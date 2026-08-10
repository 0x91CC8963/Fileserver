import os
import hashlib

# Folder containing files
folder_path = r"."

def md5sum(filepath, chunk_size=8192):
    hash_md5 = hashlib.md5()

    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hash_md5.update(chunk)

    return hash_md5.hexdigest()

for filename in os.listdir(folder_path):
    old_path = os.path.join(folder_path, filename)

    # Skip directories
    if not os.path.isfile(old_path):
        continue

    # Calculate MD5
    file_hash = md5sum(old_path)

    # Preserve extension
    _, ext = os.path.splitext(filename)

    new_filename = f"{file_hash}{ext}"
    new_path = os.path.join(folder_path, new_filename)

    # Handle collisions
    counter = 1
    while os.path.exists(new_path):
        new_filename = f"{file_hash}_{counter}{ext}"
        new_path = os.path.join(folder_path, new_filename)
        counter += 1

    os.rename(old_path, new_path)
    print(f"Renamed: {filename} -> {new_filename}")

print("Done.")