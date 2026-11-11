"""Patch-based token rules (Anthropic 28 px, OpenAI 32 px + multiplier)."""

from __future__ import annotations

import math

from . import RuleResult


def _claude_tokens(w: int, h: int, patch: int) -> int:
    return math.ceil(w / patch) * math.ceil(h / patch)


def anthropic_resize(w: int, h: int, patch: int, max_edge: int, max_tokens: int) -> tuple[int, int]:
    """Reference resize from the Anthropic docs: largest aspect-preserving size within both caps.

    Binary search on the long edge; the short edge is ``round``-ed (Python's round, as in the
    reference code).
    """

    def fits(a: int, b: int) -> bool:
        return (math.ceil(a / patch) * patch <= max_edge and math.ceil(b / patch) * patch <= max_edge
                and _claude_tokens(a, b, patch) <= max_tokens)

    if fits(w, h):
        return w, h
    if h > w:
        rh, rw = anthropic_resize(h, w, patch, max_edge, max_tokens)
        return rw, rh
    ar = w / h
    lo, hi = 1, w
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if fits(mid, max(round(mid / ar), 1)):
            lo = mid
        else:
            hi = mid
    return lo, max(round(lo / ar), 1)


def anthropic(w: int, h: int, p: dict) -> RuleResult:
    sw, sh = anthropic_resize(w, h, p["patch"], p["max_edge"], p["max_tokens"])
    return RuleResult(sent=(sw, sh), tokens=_claude_tokens(sw, sh, p["patch"]))


def openai(w: int, h: int, p: dict) -> RuleResult:
    """OpenAI 32 px patches: shrink to max_dim, cap patches (approximate rounding), multiply.

    The docs say "scale down proportionally, round down, recompute" without giving the exact
    rounding, so any estimate that needed a shrink is flagged ``approx``.
    """
    patch, budget, max_dim = p["patch"], p["patch_budget"], p["max_dim"]
    approx = False
    fw, fh = float(w), float(h)
    if max(w, h) > max_dim:
        s = max_dim / max(w, h)
        fw, fh = fw * s, fh * s
        approx = True
    cw, ch = max(1, math.floor(fw)), max(1, math.floor(fh))
    patches = math.ceil(cw / patch) * math.ceil(ch / patch)
    if patches > budget:
        approx = True
        s = math.sqrt(budget * patch * patch / (fw * fh))
        while True:
            cw, ch = max(1, math.floor(fw * s)), max(1, math.floor(fh * s))
            patches = math.ceil(cw / patch) * math.ceil(ch / patch)
            if patches <= budget:
                break
            s *= 0.999
    tokens = math.ceil(patches * p["multiplier"])
    return RuleResult(sent=(cw, ch), tokens=tokens, approx=approx, approx_code="approx_rounding")
