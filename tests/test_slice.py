"""AC-6: readable slicing of long screenshots (numbers match the research probe)."""

from __future__ import annotations

import pytest
from PIL import Image

from pixelbudget import InvalidOverlapError, fit_size, plan_slices, slice_image


def test_tall_screenshot_plan():
    fit_plan = fit_size((1170, 9000), "claude-standard")
    assert fit_plan.size == (204, 1568)
    assert round(fit_plan.scale, 3) == 0.174

    plan = plan_slices((1170, 9000), "claude-standard")
    assert plan.piece_length == 1036 and plan.overlap == 64 and len(plan.pieces) == 10
    assert all(not p.server_downscaled and p.scale == 1.0 for p in plan.pieces)
    assert plan.total_tokens == 14364
    assert plan.axis == "vertical"
    assert plan.warnings == ()


def test_boxes_cover_the_image_with_overlap():
    plan = plan_slices((1170, 9000), "claude-standard")
    assert plan.pieces[0].box[1] == 0 and plan.pieces[-1].box[3] == 9000
    for a, b in zip(plan.pieces, plan.pieces[1:]):
        assert b.box[1] == a.box[3] - 64, "consecutive pieces overlap by exactly 64 px"


def test_many_images_warning():
    plan = plan_slices((1170, 30000), "claude-standard")
    assert len(plan.pieces) > 20
    assert "many_images" in plan.warnings


def test_slice_image_crops_real_pixels():
    img = Image.new("RGB", (1170, 9000), "white")
    res = slice_image(img, "claude-standard")
    assert [im.size for im in res.images][:2] == [(1170, 1036), (1170, 1036)]
    assert res.images[-1].size == (1170, 9000 - res.plan.pieces[-1].box[1])


def test_short_image_is_one_piece():
    plan = plan_slices((800, 600), "claude-standard")
    assert len(plan.pieces) == 1 and plan.pieces[0].box == (0, 0, 800, 600)


def test_wide_image_slices_horizontally():
    plan = plan_slices((9000, 1170), "claude-standard")
    assert plan.axis == "horizontal" and len(plan.pieces) == 10
    assert plan.pieces[-1].box[2] == 9000


def test_invalid_overlap():
    with pytest.raises(InvalidOverlapError):
        plan_slices((1170, 9000), "claude-standard", overlap=-1)
    with pytest.raises(InvalidOverlapError):
        plan_slices((1170, 9000), "claude-standard", overlap=5000)
