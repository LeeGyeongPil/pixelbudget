"""Folder/file reports: one row per image x model."""

from __future__ import annotations

import errno
import os
from pathlib import Path
from typing import Iterable, Sequence

from .errors import PixelBudgetError, UnreadableImageError
from .estimate import estimate
from .registry import get_model
from .types import ReportResult, ReportRow

IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"})


def _as_list(value, name: str) -> list:
    """Accept a lone ``str``/path as a one-item list instead of iterating it character by character."""
    if isinstance(value, (str, os.PathLike)):
        return [value]
    if not isinstance(value, Iterable):
        raise TypeError(f"{name} must be a path or an iterable of paths/names, got {type(value).__name__}.")
    return list(value)


def iter_image_paths(paths: Iterable[str | os.PathLike]) -> list[str]:
    """Expand directories (recursively, sorted) and keep only files with an image extension."""
    out: list[str] = []
    for raw in _as_list(paths, "paths"):
        p = Path(raw)
        if p.is_dir():
            for child in sorted(p.rglob("*")):
                if child.is_file() and child.suffix.lower() in IMAGE_EXTENSIONS:
                    out.append(child.as_posix())
        elif p.suffix.lower() in IMAGE_EXTENSIONS:
            out.append(p.as_posix())
        elif not p.exists():
            # errno·filename 을 채운 표준 형태로 올려 CLI 가 경로를 꺼내 번역할 수 있게 한다.
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), os.fspath(raw))
    return out


def build_report(paths: Iterable[str | os.PathLike], models: Sequence[str], *,
                 detail: str | None = None, max_tokens: int | None = None,
                 prices: dict[str, float] | None = None) -> ReportResult:
    """Estimate every image under ``paths`` for every model. Unreadable files are listed in ``skipped``."""
    paths = _as_list(paths, "paths")
    models = _as_list(models, "models")
    if not models:
        raise PixelBudgetError(key="no_models")
    specs = [get_model(m) for m in models]  # fail early on unknown models
    price_by_name = {get_model(k).name: v for k, v in (prices or {}).items()}
    rows: list[ReportRow] = []
    skipped: list[str] = []
    for path in iter_image_paths(paths):
        for spec in specs:
            try:
                est = estimate(path, spec.name, detail=detail)
            except UnreadableImageError:
                skipped.append(path)
                break
            sw, sh = est.sent_size
            ow, oh = est.original_size
            price = price_by_name.get(spec.name)
            rows.append(ReportRow(
                path=path, model=est.model, original_size=est.original_size, sent_size=est.sent_size,
                tokens=est.tokens, server_downscaled=est.server_downscaled,
                wasted_pixels=max(0, ow * oh - sw * sh) if est.server_downscaled else 0,
                over_budget=max_tokens is not None and est.tokens > max_tokens,
                cost_usd=None if price is None else est.tokens * price / 1_000_000,
                confidence=est.confidence, warnings=est.warnings,
            ))
    return ReportResult(rows=tuple(rows), skipped=tuple(skipped))


def report(paths: Iterable[str | os.PathLike], models: Sequence[str], *, detail: str | None = None,
           max_tokens: int | None = None, prices: dict[str, float] | None = None) -> list[ReportRow]:
    """Like :func:`build_report` but returns only the rows."""
    return list(build_report(paths, models, detail=detail, max_tokens=max_tokens, prices=prices).rows)
