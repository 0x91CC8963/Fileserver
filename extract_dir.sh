#!/bin/bash

SOURCE_DIR="."

cd "$SOURCE_DIR" || exit

for archive in *.tar.zst; do
    archive_name="${archive%.tar.zst}"

    tar --zstd -xf "$archive"

    echo "Extracted $archive into $archive_name/"
done
