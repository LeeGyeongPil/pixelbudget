"""Pins for the formulas and table values, taken from the providers' documented examples.

Expected numbers come from the docs (see docs/model-table.md for the sources), not from the
implementation's own search, so a wrong table value or rounding direction fails here.
"""

from __future__ import annotations

import math

import pytest

from pixelbudget import estimate


def _patches(size, patch):
    return math.ceil(size[0] / patch) * math.ceil(size[1] / patch)


@pytest.mark.parametrize("model", ["gpt-5.5", "gpt-5.4"])
def test_openai_patch_budget_2500_is_the_cap_and_is_nearly_used(model):
    est = estimate((2048, 2048), model, detail="high")
    patches = _patches(est.sent_size, 32)
    assert patches <= 2500  # documented high-detail budget
    assert patches > 2400  # proportional shrink, not a much smaller image
    assert est.sent_size == (1600, 1600) and est.tokens == 3000  # implementation value (approx)
    assert est.confidence == "approx"


def test_openai_patch_original_budget_10000():
    est = estimate((4000, 4000), "gpt-5.5", detail="original")
    patches = _patches(est.sent_size, 32)
    assert 9700 < patches <= 10000
    assert est.confidence == "approx"


def test_openai_patch_tokens_round_up():
    # 32x32 = 1 patch x 1.2 = 1.2 -> 2 (round up; plain rounding would give 1)
    assert estimate((32, 32), "gpt-5.5", detail="high").tokens == 2
    # 1024x1024 = 1024 patches x 1.2 = 1228.8 -> 1229
    assert estimate((1024, 1024), "gpt-5.5", detail="high").tokens == 1229
    assert estimate((1024, 1024), "gpt-5.2").tokens == 1229
    # gpt-4.1-mini multiplier is 1.62: 1024 x 1.62 = 1658.88 -> 1659
    assert estimate((1024, 1024), "gpt-4.1-mini").tokens == 1659
    # 1 patch x 1.62 = 1.62 -> 2
    assert estimate((32, 32), "gpt-4.1-mini").tokens == 2


@pytest.mark.parametrize("model, base, tile", [
    ("gpt-4o", 85, 170), ("gpt-4.1", 85, 170), ("gpt-5", 70, 140), ("gpt-5.1", 70, 140),
    ("o1", 75, 150), ("o1-pro", 75, 150), ("o3", 75, 150), ("gpt-4o-mini", 2833, 5667),
])
def test_openai_tile_table(model, base, tile):
    # 1024x1024 -> 768x768 -> 2x2 = 4 tiles; detail=low is the base cost only.
    est = estimate((1024, 1024), model)
    assert est.sent_size == (768, 768) and est.tokens == base + 4 * tile
    assert estimate((1024, 1024), model, detail="low").tokens == base
    # 100x100 is a single tile.
    assert estimate((100, 100), model).tokens == base + tile


@pytest.mark.parametrize("model, base, tile", [
    ("gpt-4o", 85, 170), ("gpt-4.1", 85, 170), ("gpt-5", 70, 140), ("gpt-5.1", 70, 140),
    ("o1", 75, 150), ("o1-pro", 75, 150), ("o3", 75, 150), ("gpt-4o-mini", 2833, 5667),
])
def test_openai_tile_box_is_2048(model, base, tile):
    # Documented rule (developers.openai.com/api/docs/guides/images-vision, checked 2026-11-11):
    # "Scale down to fit in a 2048px x 2048px square" -> 4096x1024 becomes 2048x512. The short
    # side (512) is under 768, so no second step; 2048/512 x 512/512 = 4 tiles -> base + 4 x tile.
    # A 1536 box would give 1536x384 and 3 tiles, so this pins the 2048 value on every tile row.
    est = estimate((4096, 1024), model)
    assert est.sent_size == (2048, 512) and est.tokens == base + 4 * tile
    # Tall variant: same rule on the other axis.
    assert estimate((1024, 4096), model).sent_size == (512, 2048)


def test_openai_tile_box_scale_truncates():
    # Implementation value (the docs do not say how the box step rounds): 4096x1023 x 0.5 = 2048x511.5
    # is truncated to 511, like the documented "round down" of the short-side step. round() would give 512.
    assert estimate((4096, 1023), "gpt-4o").sent_size == (2048, 511)


def test_openai_tile_docs_example_2048x4096():
    est = estimate((2048, 4096), "gpt-4o")
    assert est.sent_size == (768, 1536) and est.tokens == 1105  # 6 tiles, documented


def test_gemini2_tiles_of_768_round_up():
    # AI Studio rule: both edges <= 384 -> 258; otherwise 258 per 768x768 tile (approx).
    assert estimate((384, 384), "gemini-2").tokens == 258
    assert estimate((1000, 1000), "gemini-2").tokens == 4 * 258  # 2 x 2 tiles
    assert estimate((1500, 800), "gemini-2").tokens == 4 * 258  # ceil(1500/768)=2, ceil(800/768)=2
    assert estimate((768, 768), "gemini-2").tokens == 258  # exactly one tile
    assert estimate((769, 768), "gemini-2").tokens == 2 * 258


@pytest.mark.parametrize("detail, tokens", [("low", 280), ("medium", 560), ("high", 1120), ("ultra_high", 2240)])
def test_gemini3_media_resolution_tokens(detail, tokens):
    assert estimate((1920, 1080), "gemini-3", detail=detail).tokens == tokens


@pytest.mark.parametrize("size, model, sent, tokens", [
    ((1075, 1520), "claude-standard", (924, 1307), 1551),  # docs example
    ((1920, 1080), "claude-standard", (1456, 819), 1560),  # docs example
    ((1000, 1000), "claude-standard", (1000, 1000), 1296),
    ((200, 200), "claude-standard", (200, 200), 64),
    ((1920, 1080), "claude-high", (1920, 1080), 2691),
    ((3840, 2160), "claude-high", (2576, 1449), 4784),
])
def test_claude_documented_examples(size, model, sent, tokens):
    est = estimate(size, model)
    assert (est.sent_size, est.tokens, est.confidence) == (sent, tokens, "documented")


@pytest.mark.parametrize("size, sent", [
    # Computed with the binary-search reference code from the Anthropic docs (vision-coordinates);
    # the short edge is round()-ed. Truncating instead of rounding gives 855 / 1390 here.
    ((1800, 1100), (1400, 856)),
    ((1920, 1200), (1389, 868)),
    ((2200, 1300), (1422, 840)),
])
def test_claude_short_edge_is_rounded_like_the_reference_code(size, sent):
    assert estimate(size, "claude-standard").sent_size == sent
