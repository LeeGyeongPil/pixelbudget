"""Self-contained demo on a synthetic tall screenshot (generated at run time, no files shipped)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .fit import fit
from .slicing import slice_image


def make_tall_screenshot(width: int = 1170, height: int = 9000) -> Image.Image:
    """Draw numbered text lines on a white page: a stand-in for a long mobile page capture."""
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=22)
    except TypeError:  # very old Pillow without a sized default font
        font = ImageFont.load_default()
    for i, y in enumerate(range(10, height - 30, 44)):
        draw.text((24, y), f"{i:03d}  The quick brown fox jumps over the lazy dog 0123456789", fill="black", font=font)
    return img


def run_demo(out_dir: str | Path, model: str = "claude-standard"):
    """Fit and slice the synthetic screenshot, write fit.png / slice-01.png / compare.png.

    Returns ``(source_size, fit_result, slice_result)``.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    img = make_tall_screenshot()
    fitted = fit(img, model)
    sliced = slice_image(img, model)
    fitted.image.save(out / "fit.png")
    sliced.images[0].save(out / "slice-01.png")
    # Side by side: what the model would see of the same page, fit (left) vs first slice (right).
    piece = sliced.images[0]
    shown = fitted.image.crop((0, 0, fitted.image.width, min(fitted.image.height, piece.height)))
    canvas = Image.new("RGB", (shown.width + 24 + piece.width, piece.height), "white")
    canvas.paste(shown, (0, 0))
    canvas.paste(piece, (shown.width + 24, 0))
    canvas.save(out / "compare.png")
    return img.size, fitted, sliced
