"""AC-4: fit finds the largest size within budget."""

from __future__ import annotations

import pytest
from PIL import Image

from pixelbudget import InvalidBudgetError, fit, fit_size
from pixelbudget.estimate import apply_rule
from pixelbudget.registry import get_model, resolve_detail

SIZES = [(1920, 1080), (1170, 9000), (800, 600), (3000, 4000)]
MODELS = [("claude-standard", None), ("gpt-4o", None), ("gpt-5.5", "high")]
BUDGETS = [600, 1000, 1500, 3000]


def _rule(model, size, detail):
    spec = get_model(model)
    _, params = resolve_detail(spec, detail)
    return apply_rule(spec, params, size)


@pytest.mark.parametrize("model,detail", MODELS)
@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("budget", BUDGETS)
def test_fit_is_within_budget_and_maximal(model, detail, size, budget):
    plan = fit_size(size, model, budget=budget, detail=detail)
    res = _rule(model, plan.size, detail)
    assert res.tokens <= budget
    assert plan.tokens == res.tokens
    assert res.sent == plan.size, "the fitted size must not be downscaled by the server"
    # aspect ratio kept within 1 px
    long_orig, short_orig = max(size), min(size)
    long_new, short_new = max(plan.size), min(plan.size)
    assert long_new <= long_orig
    assert abs(short_new - long_new * short_orig / long_orig) <= 1
    if plan.changed:
        # maximality: one more pixel on the long edge breaks the budget or the provider limit
        bigger_long = long_new + 1
        if bigger_long <= long_orig:
            w, h = size
            if w >= h:
                bigger = (bigger_long, max(1, round(bigger_long * h / w)))
            else:
                bigger = (max(1, round(bigger_long * w / h)), bigger_long)
            r2 = _rule(model, bigger, detail)
            assert r2.tokens > budget or r2.sent != bigger
    else:
        assert plan.size == size


def test_fit_without_budget_uses_provider_limits():
    plan = fit_size((1920, 1080), "claude-standard")
    assert plan.size == (1456, 819) and plan.tokens == 1560 and plan.reason == "resized_to_limits"


def test_fit_already_fits_is_unchanged():
    plan = fit_size((400, 300), "claude-standard", budget=5000)
    assert not plan.changed and plan.reason == "already_fits" and plan.size == (400, 300)


@pytest.mark.parametrize("model,detail", MODELS)
def test_pillow_output_matches_plan(model, detail):
    img = Image.new("RGB", (1920, 1080), "white")
    result = fit(img, model, budget=700, detail=detail)
    assert result.image.size == result.plan.size
    assert result.plan.changed


def test_fit_accepts_a_path(make_image):
    path = make_image("a.png", (1920, 1080))
    result = fit(path, "claude-standard", budget=800)
    assert result.image.size == (1046, 588)


def test_budget_below_model_minimum_raises():
    with pytest.raises(InvalidBudgetError, match="minimum"):
        fit_size((1000, 1000), "gpt-4o", budget=254)  # 85 base + 170 for one tile = 255
    assert fit_size((1000, 1000), "gpt-4o", budget=255).tokens == 255


def test_non_positive_budget_raises():
    for bad in (0, -5):
        with pytest.raises(InvalidBudgetError, match="positive"):
            fit_size((100, 100), "claude-standard", budget=bad)
