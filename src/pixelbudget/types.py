"""Public data types (all frozen dataclasses)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Union

from PIL import Image

Size = tuple[int, int]
ImageSource = Union[str, os.PathLike, Image.Image, Size]


@dataclass(frozen=True)
class ModelSpec:
    """One row of the model table (``data/models.json``)."""

    name: str
    provider: str
    method: str  # "patch" | "tile" | "fixed"
    family: str  # rule variant inside the method, e.g. "anthropic" / "openai" / "gemini"
    detail_rules: dict[str, dict[str, Any]]
    default_detail: str
    detail_aliases: dict[str, str]
    aliases: tuple[str, ...]
    source_url: str
    checked: str
    confidence: str  # "documented" | "measured" | "approx"
    notes: tuple[str, ...] = ()
    known_mismatches: tuple[dict[str, Any], ...] = ()
    origin: str = "builtin"  # "builtin" | "user" (row came from a models file)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "provider": self.provider,
            "method": self.method,
            "family": self.family,
            "default_detail": self.default_detail,
            "details": sorted(self.detail_rules),
            "aliases": list(self.aliases),
            "source_url": self.source_url,
            "checked": self.checked,
            "confidence": self.confidence,
            "notes": list(self.notes),
            "origin": self.origin,
        }


@dataclass(frozen=True)
class Estimate:
    """Token estimate for one image on one model."""

    model: str
    method: str
    detail: str
    original_size: Size
    sent_size: Size  # size the server will actually process (before any padding)
    tokens: int
    server_downscaled: bool
    confidence: str
    source_url: str
    warnings: tuple[str, ...] = ()  # stable codes, see ``WARNING_CODES``
    notes: tuple[str, ...] = ()  # "<code>: english message"

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "method": self.method,
            "detail": self.detail,
            "original_size": list(self.original_size),
            "sent_size": list(self.sent_size),
            "tokens": self.tokens,
            "server_downscaled": self.server_downscaled,
            "confidence": self.confidence,
            "source_url": self.source_url,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class FitPlan:
    size: Size
    tokens: int
    scale: float
    changed: bool
    # "already_fits" | "resized_to_budget" | "resized_to_limits" | "fixed_per_image"
    reason: str
    hint: str = ""  # english hint
    suggest: tuple[str, int] | None = None  # (detail name, tokens) that would fit a fixed-token budget
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class FitResult:
    image: Image.Image
    plan: FitPlan


@dataclass(frozen=True)
class Piece:
    index: int
    box: tuple[int, int, int, int]  # left, top, right, bottom in source pixels
    size: Size
    tokens: int
    scale: float  # sent width / piece width (1.0 = no server downscale)
    server_downscaled: bool


@dataclass(frozen=True)
class SlicePlan:
    pieces: tuple[Piece, ...]
    total_tokens: int
    whole_tokens: int  # tokens if the image were sent as one piece
    piece_length: int  # length of a full piece along the sliced axis
    overlap: int
    axis: str  # "vertical" | "horizontal"
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class SliceResult:
    images: list[Image.Image]
    plan: SlicePlan


@dataclass(frozen=True)
class ReportRow:
    path: str
    model: str
    original_size: Size
    sent_size: Size
    tokens: int
    server_downscaled: bool
    wasted_pixels: int  # pixels uploaded but dropped by the server downscale
    over_budget: bool
    cost_usd: float | None
    confidence: str
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "model": self.model,
            "original_size": list(self.original_size),
            "sent_size": list(self.sent_size),
            "tokens": self.tokens,
            "server_downscaled": self.server_downscaled,
            "wasted_pixels": self.wasted_pixels,
            "over_budget": self.over_budget,
            "cost_usd": self.cost_usd,
            "confidence": self.confidence,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class ReportResult:
    rows: tuple[ReportRow, ...]
    skipped: tuple[str, ...] = field(default=())


WARNING_CODES = (
    "server_downscaled",
    "fixed_per_image",
    "slice_increases_tokens",
    "many_images",
    "approx_rounding",
    "approx_rule",
    "docs_table_mismatch",
    "decompression_guard",
    "user_model_row",
)
