"""Budget fit: the largest aspect-preserving size within a token budget and the provider limits."""

from __future__ import annotations

import os

from PIL import Image

from . import registry
from .errors import InvalidBudgetError
from .estimate import apply_rule
from .measure import load_for_decode, measure
from .types import FitPlan, FitResult, ImageSource, Size

_MEDIA_RES_ORDER = ("low", "medium", "high", "ultra_high")


def _scaled(size: Size, long_edge: int) -> Size:
    """Size whose long edge is ``long_edge``, keeping the aspect ratio (short edge rounded)."""
    w, h = size
    if w >= h:
        return long_edge, max(1, round(long_edge * h / w))
    return max(1, round(long_edge * w / h)), long_edge


def _fixed_suggestion(spec, budget: int) -> tuple[str, int] | None:
    """Highest media_resolution-style detail whose fixed token count fits the budget."""
    best = None
    for name in _MEDIA_RES_ORDER:
        rule = spec.detail_rules.get(name)
        if rule and rule["tokens"] <= budget:
            best = (name, rule["tokens"])
    return best


def fit_size(size: Size, model: str, *, budget: int | None = None, detail: str | None = None) -> FitPlan:
    """Compute the largest size that costs at most ``budget`` tokens and is not downscaled by the server.

    ``budget=None`` means "only the provider limits". Never upscales. Fixed-per-image models
    (Gemini 3+) are returned unchanged with ``reason="fixed_per_image"``.
    """
    spec = registry.get_model(model)
    _, params = registry.resolve_detail(spec, detail)
    size = measure(size)
    if budget is not None and (not isinstance(budget, int) or budget <= 0):
        raise InvalidBudgetError(budget=budget)

    current = apply_rule(spec, params, size)

    if spec.method == "fixed":
        suggest = None
        hint = "Tokens are fixed per image; resizing only saves upload bytes."
        if budget is not None and current.tokens > budget:
            suggest = _fixed_suggestion(spec, budget)
            if suggest:
                hint = (f"Resizing cannot reduce tokens (fixed per image). To fit {budget}, set "
                        f"media_resolution {suggest[0]} ({suggest[1]}).")
            else:
                hint = (f"Resizing cannot help: tokens are fixed per image and every media_resolution "
                        f"level is above the budget of {budget}.")
        return FitPlan(size=size, tokens=current.tokens, scale=1.0, changed=False,
                       reason="fixed_per_image", hint=hint, suggest=suggest,
                       warnings=("fixed_per_image",))

    def ok(s: Size) -> bool:
        r = apply_rule(spec, params, s)
        return r.sent == s and (budget is None or r.tokens <= budget)

    if budget is not None:
        floor_tokens = apply_rule(spec, params, (1, 1)).tokens
        if budget < floor_tokens:
            raise InvalidBudgetError(key="budget_below_minimum", budget=budget, minimum=floor_tokens,
                                     model=spec.name)

    if ok(size):
        return FitPlan(size=size, tokens=current.tokens, scale=1.0, changed=False, reason="already_fits")

    long_edge = max(size)
    lo, hi = 1, long_edge  # ok(lo) is true (1x1 fits), ok(hi) is false
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if ok(_scaled(size, mid)):
            lo = mid
        else:
            hi = mid
    best = _scaled(size, lo)
    # The token count is a staircase; make sure no larger neighbour fits.
    probe = lo + 1
    while probe < long_edge and probe <= lo + 3:
        cand = _scaled(size, probe)
        if ok(cand):
            best = cand
        probe += 1
    tokens = apply_rule(spec, params, best).tokens
    reason = "resized_to_limits"
    if budget is not None and apply_rule(spec, params, size).tokens > budget:
        reason = "resized_to_budget"
    return FitPlan(size=best, tokens=tokens, scale=max(best) / long_edge, changed=True, reason=reason)


def fit(image: Image.Image | str | os.PathLike, model: str, *, budget: int | None = None,
        detail: str | None = None, resample: Image.Resampling = Image.Resampling.LANCZOS,
        max_pixels: int | None = None) -> FitResult:
    """Resize ``image`` (a PIL image or a path) to fit ``budget``; unchanged images are returned as is."""
    size = measure(image)  # header only for paths
    plan = fit_size(size, model, budget=budget, detail=detail)
    img = load_for_decode(image, max_pixels)
    if not plan.changed:
        return FitResult(image=img, plan=plan)
    return FitResult(image=img.resize(plan.size, resample), plan=plan)
