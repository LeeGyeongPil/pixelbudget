"""AC-5: resizing does not reduce fixed-per-image tokens, and the library says so."""

from __future__ import annotations

from PIL import Image

from pixelbudget import fit, slice_image
from pixelbudget.cli import main


def test_fit_keeps_size_and_explains():
    img = Image.new("RGB", (1170, 2000), "white")
    res = fit(img, "gemini-3", budget=500)
    assert res.image.size == (1170, 2000)
    assert res.plan.changed is False
    assert res.plan.reason == "fixed_per_image"
    assert res.plan.tokens == 1120
    assert res.plan.suggest == ("low", 280)


def test_slice_multiplies_tokens_and_warns():
    img = Image.new("RGB", (400, 1500), "white")
    res = slice_image(img, "gemini-3")
    n = len(res.images)
    assert n > 1
    assert res.plan.total_tokens == n * 1120
    assert "slice_increases_tokens" in res.plan.warnings
    assert res.plan.total_tokens > res.plan.whole_tokens


def test_cli_fit_prints_hint_and_writes_nothing(make_image, tmp_path, capsys):
    path = make_image("shot.png", (1170, 2000))
    code = main(["--lang", "en", "fit", path, "--model", "gemini-3", "--budget", "500"])
    out = capsys.readouterr().out
    assert code == 0
    assert "media_resolution low (280)" in out
    assert sorted(p.name for p in tmp_path.iterdir()) == ["shot.png"]
