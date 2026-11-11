"""Fixed tokens per image (Gemini 3/4 media_resolution)."""

from __future__ import annotations

from . import RuleResult


def gemini(w: int, h: int, p: dict) -> RuleResult:
    return RuleResult(sent=(w, h), tokens=p["tokens"])
