from __future__ import annotations

from pathlib import Path
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from logo_bot.config import CHANNELS, OUTPUT_SIZE
from logo_bot.image_processing import render_overlay


TMP = ROOT / "tmp" / "previews"


def make_sample() -> bytes:
    width, height = OUTPUT_SIZE
    image = Image.new("RGB", OUTPUT_SIZE, "#e7e1d8")
    draw = ImageDraw.Draw(image)
    for y in range(0, height, 90):
        color = "#d24b59" if (y // 90) % 2 == 0 else "#2f7f78"
        draw.rectangle((0, y, width, y + 45), fill=color)
    draw.rectangle((70, 95, width - 70, height - 95), outline="#161616", width=8)
    out = ROOT / "tmp" / "sample.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, format="JPEG", quality=95)
    return out.read_bytes()


def main() -> None:
    TMP.mkdir(parents=True, exist_ok=True)
    sample = make_sample()
    for channel in CHANNELS.values():
        if not channel.is_ready:
            print(f"skip {channel.key}: missing logo")
            continue
        for option in channel.options:
            content, ext, _mime = render_overlay(sample, option.path)
            output = TMP / f"{channel.key}_{option.key}.{ext}"
            output.write_bytes(content)
            print(output)


if __name__ == "__main__":
    main()
