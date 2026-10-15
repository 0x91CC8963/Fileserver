#!/usr/bin/env bash

# Usage: ./download_images.sh links.txt [output_directory]

set -u

INPUT="${1:-links.txt}"
OUTPUT="${2:-downloaded_images}"

if [[ ! -f "$INPUT" ]]; then
    echo "Error: Input file '$INPUT' not found."
    exit 1
fi

mkdir -p "$OUTPUT"

count=0
failed=0

while IFS= read -r url || [[ -n "$url" ]]; do
    # Remove Windows carriage returns and surrounding whitespace
    url="${url//$'\r'/}"
    url="${url#"${url%%[![:space:]]*}"}"
    url="${url%"${url##*[![:space:]]}"}"

    # Skip empty lines and comments
    [[ -z "$url" || "$url" == \#* ]] && continue

    # Assign a unique, predictable filename
    count=$((count + 1))
    filename=$(printf "image_%04d" "$count")
    filepath="$OUTPUT/$filename"

    echo "Downloading [$count]: $url"

    # Download to a temporary file first, then detect the file type
    if curl -fLsS --connect-timeout 15 --max-time 120 \
        --retry 2 --retry-delay 1 \
        "$url" -o "$filepath.tmp"; then

        # Determine the file extension from its actual contents
        mime=$(file --brief --mime-type "$filepath.tmp")

        case "$mime" in
            image/jpeg) ext="jpg" ;;
            image/png)  ext="png" ;;
            image/gif)  ext="gif" ;;
            image/webp) ext="webp" ;;
            image/tiff) ext="tiff" ;;
            image/bmp)  ext="bmp" ;;
            image/avif) ext="avif" ;;
            image/svg+xml) ext="svg" ;;
            *)
                echo "  Skipped: downloaded content is not a recognized image ($mime)"
                rm -f "$filepath.tmp"
                failed=$((failed + 1))
                continue
                ;;
        esac

        mv "$filepath.tmp" "$filepath.$ext"
        echo "  Saved: $filepath.$ext"
    else
        echo "  Failed to download."
        rm -f "$filepath.tmp"
        failed=$((failed + 1))
    fi

done < "$INPUT"

echo
echo "Finished."
echo "Processed: $count"
echo "Failed or skipped: $failed"
echo "Output directory: $OUTPUT"
