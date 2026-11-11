"""pixelbudget: offline image-token estimates, budget fit and readable slicing for vision LLMs."""

from __future__ import annotations

__version__ = "0.1.0"

from .errors import (
    ImageTooLargeError,
    InvalidBudgetError,
    InvalidOverlapError,
    InvalidSizeError,
    ModelTableError,
    PixelBudgetError,
    UnknownModelError,
    UnreadableImageError,
    UnsupportedDetailError,
)
from .estimate import estimate
from .fit import fit, fit_size
from .measure import measure
from .registry import get_model, list_models
from .report import build_report, report
from .slicing import plan_slices, slice_image
from .types import (
    Estimate,
    FitPlan,
    FitResult,
    ImageSource,
    ModelSpec,
    Piece,
    ReportResult,
    ReportRow,
    Size,
    SlicePlan,
    SliceResult,
)

__all__ = [
    "__version__", "estimate", "fit", "fit_size", "measure", "get_model", "list_models", "report",
    "build_report", "plan_slices", "slice_image", "Estimate", "FitPlan", "FitResult", "ImageSource",
    "ModelSpec", "Piece", "ReportResult", "ReportRow", "Size", "SlicePlan", "SliceResult",
    "PixelBudgetError", "UnknownModelError", "UnsupportedDetailError", "InvalidBudgetError",
    "InvalidOverlapError", "InvalidSizeError", "UnreadableImageError", "ImageTooLargeError",
    "ModelTableError",
]
