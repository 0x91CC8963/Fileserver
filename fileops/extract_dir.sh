#!/bin/bash

SOURCE_DIR="."

cd "$SOURCE_DIR" || exit

for archive in *.tar.gz; do
    [ -f "$archive" ] || continue

    archive_name="${archive%.tar.gz}"
    mkdir -p "$archive_name"

    tar -xzf "$archive" -C "$archive_name" || {
        echo "Failed to extract $archive"
        continue
    }

    echo "Extracted $archive into $archive_name/"
done
	