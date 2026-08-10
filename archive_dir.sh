#!/bin/bash

SOURCE_DIR="."

cd "$SOURCE_DIR" || exit

for folder in */; do
	folder_name="${folder%/}"

	tar --zstd -cvf "${folder_name}.tar.zst" "$folder_name"

	echo "Compressed $folder_name into ${folder_name}.tar.zst"
done
