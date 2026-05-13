from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from .config import OUTPUT_FORMAT, OUTPUT_QUALITY, OUTPUT_SIZE, output_extension_and_mime


def _cover_crop(image: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    target_w, target_h = target_size
    source_w, source_h = image.size
    target_ratio = target_w / target_h
    source_ratio = source_w / source_h

    if source_ratio > target_ratio:
        crop_w = int(source_h * target_ratio)
        left = (source_w - crop_w) // 2
        box = (left, 0, left + crop_w, source_h)
    else:
        crop_h = int(source_w / target_ratio)
        top = (source_h - crop_h) // 2
        box = (0, top, source_w, top + crop_h)

    cropped = image.crop(box)
    if cropped.size != target_size:
        cropped = cropped.resize(target_size, Image.Resampling.LANCZOS)
    return cropped


def render_overlay(source_bytes: bytes, overlay_path: Path) -> tuple[bytes, str, str]:
    with Image.open(BytesIO(source_bytes)) as source:
        source = ImageOps.exif_transpose(source)
        base = _cover_crop(source.convert("RGBA"), OUTPUT_SIZE)

    with Image.open(overlay_path) as overlay:
        overlay = overlay.convert("RGBA")
        if overlay.size != OUTPUT_SIZE:
            overlay = overlay.resize(OUTPUT_SIZE, Image.Resampling.LANCZOS)

        base.alpha_composite(overlay)

    ext, mime = output_extension_and_mime()
    out = BytesIO()
    if OUTPUT_FORMAT == "PNG":
        base.save(out, format="PNG", optimize=True)
    else:
        base.convert("RGB").save(
            out,
            format="JPEG",
            quality=OUTPUT_QUALITY,
            optimize=True,
            progressive=True,
        )
    return out.getvalue(), ext, mime

