from pathlib import Path
from PIL import Image

folder = Path(".")

for webp_file in folder.glob("*.webp"):
    png_file = webp_file.with_suffix(".png")

    with Image.open(webp_file) as img:
        img.save(png_file, "PNG")

    print(f"Converted: {webp_file.name} -> {png_file.name}")
