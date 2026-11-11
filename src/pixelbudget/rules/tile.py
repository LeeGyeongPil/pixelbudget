"""Tile-based token rules (OpenAI 512 px tiles, Gemini 2 768 px tiles)."""

from __future__ import annotations

import math

from . import RuleResult


def openai(w: int, h: int, p: dict) -> RuleResult:
    if p.get("low"):
        # detail=low: flat base cost; the server works on a small version of the image.
        return RuleResult(sent=(w, h), tokens=p["base"])
    sw, sh = w, h
    s = min(1.0, p["box"] / max(w, h))
    sw, sh = max(1, int(w * s)), max(1, int(h * s))
    if min(sw, sh) > p["short_side"]:
        s = p["short_side"] / min(sw, sh)
        if sw <= sh:
            sw, sh = p["short_side"], max(1, int(sh * s))
        else:
            sw, sh = max(1, int(sw * s)), p["short_side"]
    tiles = math.ceil(sw / p["tile"]) * math.ceil(sh / p["tile"])
    return RuleResult(sent=(sw, sh), tokens=p["base"] + p["tile_tokens"] * tiles)


def gemini(w: int, h: int, p: dict) -> RuleResult:
    if w <= p["small_edge"] and h <= p["small_edge"]:
        tokens = p["tokens"]
    else:
        tokens = p["tokens"] * math.ceil(w / p["tile"]) * math.ceil(h / p["tile"])
    return RuleResult(sent=(w, h), tokens=tokens, approx=True, approx_code="approx_rule")
