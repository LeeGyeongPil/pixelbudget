"""Readable slicing: cut a long image into overlapping pieces the server will not downscale."""

from __future__ import annotations

import os

from PIL import Image

from . import registry
from .errors import InvalidOverlapError
from .estimate import apply_rule
from .measure import load_for_decode, measure
from .types import Piece, SlicePlan, SliceResult, Size


def _piece_size(across: int, length: int, vertical: bool) -> Size:
    return (across, length) if vertical else (length, across)


def plan_slices(size: Size, model: str, *, overlap: int = 64, detail: str | None = None) -> SlicePlan:
    """Plan overlapping pieces along the long axis.

    The piece length is the largest one whose size is *not* downscaled by the server (edge and
    token caps together), so every piece keeps the original pixel scale. For fixed-per-image
    models there is no such limit; square pieces are used and the extra tokens are warned about.
    """
    spec = registry.get_model(model)
    _, params = registry.resolve_detail(spec, detail)
    size = measure(size)
    if not isinstance(overlap, int) or overlap < 0:
        raise InvalidOverlapError(overlap=overlap)
    w, h = size
    vertical = h >= w
    long_len, across = (h, w) if vertical else (w, h)
    warnings: list[str] = []

    whole = apply_rule(spec, params, size)

    def ok(n: int) -> bool:
        s = _piece_size(across, n, vertical)
        return apply_rule(spec, params, s).sent == s

    if spec.method == "fixed":
        length = min(long_len, across)
    elif ok(long_len):
        length = long_len
    elif not ok(1):
        # Even the thinnest strip is downscaled (the across axis alone exceeds a limit).
        length = min(long_len, across)
        warnings.append("server_downscaled")
    else:
        lo, hi = 1, long_len
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            if ok(mid):
                lo = mid
            else:
                hi = mid
        length = lo

    if length < long_len and overlap >= length:
        raise InvalidOverlapError(key="overlap_too_large", overlap=overlap, length=length, model=spec.name)

    pieces: list[Piece] = []
    start = 0
    while True:
        end = min(start + length, long_len)
        psize = _piece_size(across, end - start, vertical)
        res = apply_rule(spec, params, psize)
        box = (0, start, w, end) if vertical else (start, 0, end, h)
        sent_across = res.sent[0] if vertical else res.sent[1]
        pieces.append(Piece(index=len(pieces), box=box, size=psize, tokens=res.tokens,
                            scale=sent_across / across, server_downscaled=res.sent != psize))
        if end >= long_len:
            break
        start = end - overlap

    total = sum(p.tokens for p in pieces)
    if spec.method == "fixed" and len(pieces) > 1:
        warnings.append("slice_increases_tokens")
    if spec.provider == "anthropic" and len(pieces) > 20:
        warnings.append("many_images")
    return SlicePlan(pieces=tuple(pieces), total_tokens=total, whole_tokens=whole.tokens,
                     piece_length=length, overlap=overlap,
                     axis="vertical" if vertical else "horizontal", warnings=tuple(warnings))


def slice_image(image: Image.Image | str | os.PathLike, model: str, *, overlap: int = 64,
                detail: str | None = None, max_pixels: int | None = None) -> SliceResult:
    """Cut ``image`` (PIL image or path) into the pieces of :func:`plan_slices`."""
    plan = plan_slices(measure(image), model, overlap=overlap, detail=detail)
    img = load_for_decode(image, max_pixels)
    return SliceResult(images=[img.crop(p.box) for p in plan.pieces], plan=plan)
