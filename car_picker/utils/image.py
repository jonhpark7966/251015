"""Image handling helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

from PIL import Image


def ensure_thumbnail(image_path: Path, cache_dir: Path, *, max_width: int) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    thumb_name = f"{image_path.stem}_{max_width}px.jpg"
    thumb_path = cache_dir / thumb_name

    if not thumb_path.exists() or thumb_path.stat().st_mtime < image_path.stat().st_mtime:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            width, height = img.size
            if width > max_width:
                ratio = max_width / float(width)
                new_size: Tuple[int, int] = (max_width, int(height * ratio))
                img = img.resize(new_size, Image.LANCZOS)
            img.save(thumb_path, format="JPEG", quality=85)

    return thumb_path

