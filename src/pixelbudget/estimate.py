"""Token estimation: pick the rule for a model, attach warnings and provenance."""

from __future__ import annotations

from . import registry
from .measure import exceeds_guard, measure
from .rules import RuleResult
from .rules import fixed as _fixed
from .rules import patch as _patch
from .rules import tile as _tile
from .types import Estimate, ImageSource, ModelSpec, Size

_RULES = {
    ("patch", "anthropic"): _patch.anthropic,
    ("patch", "openai"): _patch.openai,
    ("tile", "openai"): _tile.openai,
    ("tile", "gemini"): _tile.gemini,
    ("fixed", "gemini"): _fixed.gemini,
}

_MESSAGES = {
    "server_downscaled": "The server will downscale this image before processing it.",
    "fixed_per_image": "Tokens are fixed per image (media_resolution): resizing does not reduce them.",
    "approx_rounding": "Rounding of the proportional shrink is not fully specified by the docs; tokens are approximate.",
    "approx_rule": "The documented rule for this model is only an approximation of billed usage.",
    "docs_table_mismatch": "The docs table and the docs' reference code disagree for this size.",
    "decompression_guard": "Pixel count is above Pillow's decompression-bomb limit; decoding needs max_pixels.",
}


def apply_rule(spec: ModelSpec, params: dict, size: Size) -> RuleResult:
    """Run the pure token rule for ``size`` (no warnings)."""
    return _RULES[(spec.method, spec.family)](size[0], size[1], params)


def estimate(source: ImageSource, model: str, *, detail: str | None = None) -> Estimate:
    """Estimate image tokens for ``source`` on ``model`` without decoding pixels.

    ``source`` may be a path, a ``PIL.Image.Image`` or a ``(width, height)`` tuple.
    """
    spec = registry.get_model(model)
    detail_name, params = registry.resolve_detail(spec, detail)
    size = measure(source)
    res = apply_rule(spec, params, size)
    downscaled = res.sent != size
    warnings: list[str] = []
    notes: list[str] = []
    confidence = spec.confidence
    if downscaled:
        warnings.append("server_downscaled")
    if spec.method == "fixed":
        warnings.append("fixed_per_image")
    if res.approx:
        warnings.append(res.approx_code)
        confidence = "approx"
    for mm in spec.known_mismatches:
        if tuple(mm["size"]) == size:
            warnings.append(mm["code"])
            notes.append(f"{mm['code']}: {mm['note']}")
    if exceeds_guard(size):
        warnings.append("decompression_guard")
    for code in warnings:
        if not any(n.startswith(code + ":") for n in notes):
            notes.append(f"{code}: {_MESSAGES[code]}")
    return Estimate(
        model=spec.name, method=spec.method, detail=detail_name, original_size=size,
        sent_size=res.sent, tokens=res.tokens, server_downscaled=downscaled,
        confidence=confidence, source_url=spec.source_url,
        warnings=tuple(warnings), notes=tuple(notes),
    )
