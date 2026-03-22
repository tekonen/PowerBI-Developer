"""Image/screenshot input processing.

Loads and prepares images for Claude vision analysis.
"""

from __future__ import annotations

from pathlib import Path

from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)


def load_image(path: Path) -> bytes:
    """Load an image file as bytes."""
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    data = path.read_bytes()
    logger.info(f"Loaded image: {path.name} ({len(data)} bytes)")
    return data


def resize_if_needed(image_bytes: bytes, max_dimension: int = 2048) -> bytes:
    """Resize image if it exceeds max dimension (for API limits)."""
    from PIL import Image
    import io

    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size

    if w <= max_dimension and h <= max_dimension:
        return image_bytes

    ratio = min(max_dimension / w, max_dimension / h)
    new_w = int(w * ratio)
    new_h = int(h * ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    result = buf.getvalue()
    logger.info(f"Resized image from {w}x{h} to {new_w}x{new_h}")
    return result
