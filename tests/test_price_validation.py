"""--price rejects negative/nan/inf; JSON output is strict standard JSON."""

from __future__ import annotations

import json

import pytest

from pixelbudget.cli import main


def _strict(text):
    def boom(c):
        raise ValueError(c)
    return json.loads(text, parse_constant=boom)


@pytest.mark.parametrize("bad", ["-1", "nan", "inf", "-inf", "Infinity"])
def test_bad_price_exits_2(bad, tmp_path, make_image, capsys):
    make_image("a.png", (300, 200))
    code = main(["--lang", "en", "report", str(tmp_path / "a.png"), "--model", "gpt-4o",
                 "--price", f"gpt-4o={bad}"])
    assert code == 2
    assert "finite number of 0 or more" in capsys.readouterr().err


@pytest.mark.parametrize("ok", ["0", "2.5"])
def test_zero_and_positive_prices_work(ok, tmp_path, make_image, capsys):
    make_image("a.png", (300, 200))
    code = main(["report", str(tmp_path / "a.png"), "--model", "gpt-4o",
                 "--price", f"gpt-4o={ok}", "--format", "json"])
    assert code == 0
    rows = _strict(capsys.readouterr().out)["rows"]
    assert rows[0]["cost_usd"] == pytest.approx(rows[0]["tokens"] * float(ok) / 1e6)


def test_models_json_is_strict(capsys):
    assert main(["models", "--format", "json"]) == 0
    _strict(capsys.readouterr().out)
