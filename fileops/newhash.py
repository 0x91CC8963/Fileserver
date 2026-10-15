import os
import json
import hashlib
import mimetypes
import stat
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed


ARCHIVE_ROOT = Path(".")
CACHE_FILE = Path(".checksum_cache.json")
MAX_WORKERS = os.cpu_count() or 4

HASH_ALGORITHMS = ("md5", "sha256", "sha512")

GENERATED_FILES = {
    "index.html",
    "checksums.md5",
    "checksums.sha256",
    "file_inventory.json",
    CACHE_FILE.name,
}

# MIME database initialization
mimetypes.init()


def iso_time(timestamp):
    """Convert a Unix timestamp to an ISO 8601 UTC string."""
    if timestamp is None:
        return None

    return datetime.fromtimestamp(
        timestamp, tz=timezone.utc
    ).isoformat()


def load_cache():
    if CACHE_FILE.exists():
        try:
            with CACHE_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            print("[WARN] Cache could not be loaded; rebuilding it.")
    return {}


def save_cache(cache):
    temp_file = CACHE_FILE.with_suffix(".tmp")

    try:
        with temp_file.open("w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, sort_keys=True)
            f.write("\n")

        os.replace(temp_file, CACHE_FILE)
    except OSError as e:
        print(f"[ERROR] Could not save cache: {e}")
        try:
            temp_file.unlink(missing_ok=True)
        except OSError:
            pass


def get_file_info(path):
    """Collect filesystem metadata without reading file contents."""
    s = path.stat()
    mime_type, _ = mimetypes.guess_type(path.name)

    # st_birthtime exists on some platforms, but not all.
    birthtime = getattr(s, "st_birthtime", None)

    return {
        "name": path.name,
        "extension": path.suffix.lower() or None,
        "mime_type": mime_type,
        "size_bytes": s.st_size,
        "modified_at": iso_time(s.st_mtime),
        "created_at": iso_time(birthtime),
        "accessed_at": iso_time(s.st_atime),
        "changed_at": iso_time(s.st_ctime),
        "mtime_ns": s.st_mtime_ns,
        "ctime_ns": s.st_ctime_ns,
        "device_id": s.st_dev,
        "inode": s.st_ino,
        "mode": stat.S_IMODE(s.st_mode),
        "is_readonly": not bool(s.st_mode & stat.S_IWUSR),
        "is_empty": s.st_size == 0,
        "is_hidden": path.name.startswith("."),
        "is_executable": os.access(path, os.X_OK),
        "owner_uid": getattr(s, "st_uid", None),
        "owner_gid": getattr(s, "st_gid", None),
        "allocated_bytes": getattr(s, "st_blocks", 0) * 512,
    }


def cache_signature(info):
    """Fields used to determine whether a file needs rehashing."""
    return {
        "size_bytes": info["size_bytes"],
        "mtime_ns": info["mtime_ns"],
        "ctime_ns": info["ctime_ns"],
        "device_id": info["device_id"],
        "inode": info["inode"],
    }


def hash_file(path):
    """Calculate all configured hashes in one pass."""
    hashes = {
        algo: hashlib.new(algo)
        for algo in HASH_ALGORITHMS
    }

    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break

            for h in hashes.values():
                h.update(chunk)

    return {algo: h.hexdigest() for algo, h in hashes.items()}


def hash_file_safely(path):
    """
    Avoid recording hashes if the file changes during hashing.
    This detects ordinary concurrent modifications, not every
    possible filesystem race.
    """
    before = path.stat()
    hashes = hash_file(path)
    after = path.stat()

    before_signature = (
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
        before.st_ino,
        before.st_dev,
    )
    after_signature = (
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
        after.st_ino,
        after.st_dev,
    )

    if before_signature != after_signature:
        raise RuntimeError("File changed while being hashed")

    return hashes


def relative_path(path):
    return path.relative_to(ARCHIVE_ROOT.resolve()).as_posix()


def process_folder(folder, cache, executor):
    folder_path = Path(folder)
    records = []
    futures = {}

    try:
        entries = sorted(
            folder_path.iterdir(),
            key=lambda p: p.name.casefold()
        )
    except OSError as e:
        print(f"[ERROR] Could not list directory {folder}: {e}")
        return

    for entry in entries:
        if entry.name in GENERATED_FILES:
            continue

        # Do not follow symlinks or recurse into subdirectories here.
        if entry.is_symlink():
            print(f"[SKIP] Symlink: {entry}")
            continue

        try:
            if not entry.is_file():
                continue

            info = get_file_info(entry)
            key = str(entry.resolve())
            signature = cache_signature(info)
            cached = cache.get(key)

            record = {
                "path": relative_path(entry),
                **info,
            }

            if (
                isinstance(cached, dict)
                and cached.get("signature") == signature
                and all(a in cached.get("hashes", {})
                        for a in HASH_ALGORITHMS)
            ):
                record["hashes"] = cached["hashes"]
                record["hash_status"] = "cached"
                records.append(record)
                print(f"[CACHE] {entry}")
            else:
                future = executor.submit(hash_file_safely, entry)
                futures[future] = (
                    key, entry, signature, record
                )

        except OSError as e:
            print(f"[ERROR] Could not inspect {entry}: {e}")

    for future in as_completed(futures):
        key, entry, signature, record = futures[future]

        try:
            hashes = future.result()

            cache[key] = {
                "signature": signature,
                "hashes": hashes,
            }

            record["hashes"] = hashes
            record["hash_status"] = "hashed"
            records.append(record)
            print(f"[HASHED] {entry}")

        except Exception as e:
            print(f"[ERROR] Could not hash {entry}: {e}")

    # Stable ordering for reproducible inventory output.
    records.sort(key=lambda r: r["path"].casefold())

    # Add duplicate-content groups based on SHA-256.
    groups = {}
    for record in records:
        sha = record.get("hashes", {}).get("sha256")
        if sha:
            groups.setdefault(sha, []).append(record["path"])

    for record in records:
        sha = record.get("hashes", {}).get("sha256")
        paths = groups.get(sha, []) if sha else []
        record["duplicate_count"] = len(paths)
        record["duplicate_paths"] = (
            paths if len(paths) > 1 else []
        )

    # Existing checksum formats remain compatible.
    md5_lines = []
    sha_lines = []

    for record in records:
        hashes = record.get("hashes")
        if not hashes:
            continue

        name = record["name"]
        md5_lines.append(f'{hashes["md5"]}  {name}')
        sha_lines.append(f'{hashes["sha256"]}  {name}')

    for filename, lines in (
        ("checksums.md5", md5_lines),
        ("checksums.sha256", sha_lines),
    ):
        output = folder_path / filename
        try:
            if lines:
                output.write_text(
                    "\n".join(sorted(lines)) + "\n",
                    encoding="utf-8",
                )
            else:
                output.unlink(missing_ok=True)

            print(f"[OK] Written: {output}")
        except OSError as e:
            print(f"[ERROR] Could not write {output}: {e}")

    inventory = {
        "schema_version": 1,
        "directory": relative_path(folder_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "file_count": len(records),
        "total_size_bytes": sum(
            r["size_bytes"] for r in records
        ),
        "empty_file_count": sum(
            r["is_empty"] for r in records
        ),
        "files": records,
    }

    inventory_path = folder_path / "file_inventory.json"

    try:
        temp_path = inventory_path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(inventory, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(temp_path, inventory_path)
        print(f"[OK] Inventory written: {inventory_path}")
    except OSError as e:
        print(f"[ERROR] Could not write inventory: {e}")


def cleanup_cache(cache):
    """Remove cached entries for files that no longer exist."""
    stale = [
        path for path in cache
        if not Path(path).exists()
    ]

    for path in stale:
        del cache[path]

    if stale:
        print(f"[CLEANUP] Removed {len(stale)} stale entries")


def build():
    root = ARCHIVE_ROOT.resolve()
    cache = load_cache()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for current_root, dirs, _ in os.walk(root):
            # Avoid traversing symlinked directories.
            dirs[:] = sorted(
                d for d in dirs
                if not (Path(current_root) / d).is_symlink()
            )

            process_folder(current_root, cache, executor)
            print(f"[OK] Checksums generated: {current_root}")

    cleanup_cache(cache)
    save_cache(cache)


if __name__ == "__main__":
    build()