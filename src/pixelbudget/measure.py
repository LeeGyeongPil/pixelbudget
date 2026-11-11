"""Header-only image size measurement (no pixel decoding)."""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from typing import Iterator

from PIL import Image, UnidentifiedImageError

from .errors import ImageTooLargeError, InvalidSizeError, UnreadableImageError
from .types import ImageSource, Size

_ORIENTATION_TAG = 0x0112
_SWAP_ORIENTATIONS = {5, 6, 7, 8}  # 90/270 degree rotations swap width and height
_LOCK = threading.Lock()


@contextmanager
def _guard_disabled() -> Iterator[None]:
    """``Image.open`` itself raises past 2x MAX_IMAGE_PIXELS; we only read the header, so lift it."""
    with _LOCK:
        saved = Image.MAX_IMAGE_PIXELS
        Image.MAX_IMAGE_PIXELS = None
        try:
            yield
        finally:
            Image.MAX_IMAGE_PIXELS = saved


def _orientation(img: Image.Image) -> int:
    # PNG exif lives in info (reading getexif() on a PNG may decode pixels, so avoid it).
    raw = img.info.get("exif")
    if isinstance(raw, bytes):
        exif = Image.Exif()
        try:
            exif.load(raw)
        except Exception:  # corrupt exif is not worth failing the measurement
            return 1
        return int(exif.get(_ORIENTATION_TAG, 1) or 1)
    if img.format in ("JPEG", "MPO", "TIFF", "WEBP"):
        try:
            return int(img.getexif().get(_ORIENTATION_TAG, 1) or 1)
        except Exception:
            return 1
    return 1


def _validate(size: tuple) -> Size:
    try:
        w, h = size
        w, h = int(w), int(h)
    except (TypeError, ValueError):
        raise InvalidSizeError(key="invalid_size_pair", size=size) from None
    if w < 1 or h < 1:
        raise InvalidSizeError(key="invalid_size_positive", w=w, h=h)
    return w, h


def measure(source: ImageSource) -> Size:
    """Return the displayed (width, height) of ``source``.

    Paths are opened lazily: only the header is read and an EXIF orientation of 5-8 swaps the
    axes. ``PIL.Image`` objects and ``(w, h)`` tuples are used as they are.
    """
    if isinstance(source, Image.Image):
        return _validate(source.size)
    if isinstance(source, tuple):
        return _validate(source)
    path = os.fspath(source)
    try:
        with _guard_disabled():
            with Image.open(path) as img:
                w, h = img.size
                if _orientation(img) in _SWAP_ORIENTATIONS:
                    w, h = h, w
    except (UnidentifiedImageError, OSError) as exc:
        if isinstance(exc, FileNotFoundError):
            raise
        # 폴더를 넘긴 경우는 따로 구분해 CLI 가 "파일 하나를 지정하라"고 안내할 수 있게 한다.
        key = "unreadable_directory" if isinstance(exc, IsADirectoryError) else "unreadable_image"
        raise UnreadableImageError(key=key, path=path, reason=str(exc)) from exc
    return _validate((w, h))


def exceeds_guard(size: Size) -> bool:
    """True when the pixel count is above Pillow's default decompression-bomb warning level."""
    limit = Image.MAX_IMAGE_PIXELS
    return limit is not None and size[0] * size[1] > limit


def check_decode_allowed(size: Size, max_pixels: int | None) -> None:
    """Raise ImageTooLargeError before decoding an image whose pixel count is above the limit."""
    limit = max_pixels if max_pixels is not None else Image.MAX_IMAGE_PIXELS
    if limit is not None and size[0] * size[1] > limit:
        raise ImageTooLargeError(w=size[0], h=size[1], pixels=size[0] * size[1], limit=limit)


def load_for_decode(source, max_pixels: int | None) -> Image.Image:
    """Open and fully decode ``source`` (path or Image) after the size guard, EXIF-corrected."""
    from PIL import ImageOps

    if isinstance(source, Image.Image):
        check_decode_allowed(source.size, max_pixels)
        return source
    if isinstance(source, tuple):
        raise InvalidSizeError(key="invalid_size_tuple")
    check_decode_allowed(measure(source), max_pixels)
    with _guard_disabled():
        with Image.open(os.fspath(source)) as img:
            img.load()
            return ImageOps.exif_transpose(img)
