"""Per-method token rules. Each rule maps (width, height, params) -> RuleResult."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuleResult:
    sent: tuple[int, int]  # size the server processes
    tokens: int
    approx: bool = False
    approx_code: str = ""
