"""Create three synthetic sample images (no real screenshots needed) for the README walkthrough."""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

from pixelbudget.demo import make_tall_screenshot

out = Path(sys.argv[1] if len(sys.argv) > 1 else "samples")
out.mkdir(parents=True, exist_ok=True)

hd = Image.new("RGB", (1920, 1080), "white")
ImageDraw.Draw(hd).rectangle((60, 60, 1860, 1020), outline="black", width=6)
hd.save(out / "hd.png")
Image.new("RGB", (300, 200), "white").save(out / "small.png")
make_tall_screenshot().save(out / "tall.png")
print(f"wrote {len(list(out.glob('*.png')))} images to {out}/")
