"""CLI ``estimate`` accepts a WxH size in place of a path (an existing file or folder wins)."""

from __future__ import annotations

import json

import pytest

from pixelbudget import __version__, estimate
from pixelbudget.cli import main


def _json(capsys, *argv):
    code = main(["--lang", "en", "estimate", *argv, "--format", "json"])
    return code, json.loads(capsys.readouterr().out)


def test_size_only_table_and_tokens_match_library(capsys):
    assert main(["--lang", "en", "estimate", "1920x1080", "--model", "gpt-4o"]) == 0
    out = capsys.readouterr().out
    assert "1920x1080" in out and str(estimate((1920, 1080), "gpt-4o").tokens) in out


def test_size_only_json_and_uppercase_x(capsys):
    code, data = _json(capsys, "1920X1080", "--model", "gpt-4o")
    assert code == 0
    assert data["rows"][0]["path"] == "1920X1080"
    assert data["rows"][0]["tokens"] == estimate((1920, 1080), "gpt-4o").tokens
    assert data["summary"]["rows"] == 1


def test_mixed_inputs_keep_order_and_labels(make_image, tmp_path, capsys):
    make_image("shots/a.png", (300, 200))
    code, data = _json(capsys, "800x600", (tmp_path / "shots").as_posix(), "64x64", "--model", "claude-standard")
    assert code == 0
    assert [r["path"] for r in data["rows"]] == ["800x600", (tmp_path / "shots" / "a.png").as_posix(), "64x64"]
    assert data["rows"][1]["original_size"] == [300, 200]


def test_existing_file_wins_over_size_reading(tmp_path, monkeypatch, capsys):
    from PIL import Image

    monkeypatch.chdir(tmp_path)
    Image.new("RGB", (300, 200)).save("100x100", format="PNG")  # a file literally named 100x100
    code, data = _json(capsys, "100x100", "--model", "gpt-4o")
    # Same as before this feature: a file without an image extension is ignored, never read as a size.
    assert code == 0 and data["rows"] == []


def test_existing_folder_wins_over_size_reading(make_image, tmp_path, monkeypatch, capsys):
    make_image("640x480/pic.png", (300, 200))
    monkeypatch.chdir(tmp_path)
    code, data = _json(capsys, "640x480", "--model", "gpt-4o")
    assert code == 0 and data["rows"][0]["path"].endswith("pic.png")


@pytest.mark.parametrize("lang,text", [("en", "Width and height must be >= 1, got 0x100."),
                                       ("ko", "너비와 높이는 1 이상이어야 합니다. 받은 값: 0x100.")])
def test_zero_size_uses_invalid_size_positive_in_both_languages(lang, text, capsys):
    assert main(["--lang", lang, "estimate", "0x100"]) == 2
    err = capsys.readouterr().err
    assert text in err


@pytest.mark.parametrize("bad", ["100x", "axb", "x100"])
def test_malformed_size_is_still_file_not_found(bad, capsys):
    assert main(["--lang", "en", "estimate", bad]) == 2
    assert "No such file or directory" in capsys.readouterr().err


def test_report_does_not_accept_sizes(capsys):
    assert main(["--lang", "en", "report", "1920x1080"]) == 2
    assert "No such file or directory" in capsys.readouterr().err


@pytest.mark.parametrize("lang", ["en", "ko"])
def test_help_mentions_wxh_only_for_estimate_and_fits_80_columns(lang, capsys):
    with pytest.raises(SystemExit):
        main(["--lang", lang, "estimate", "--help"])
    est_help = capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["--lang", lang, "report", "--help"])
    rep_help = capsys.readouterr().out
    assert "WxH" in est_help and "WxH" not in rep_help
    assert max(len(line) for line in est_help.splitlines()) <= 80


def test_version_is_0_3_0(capsys):
    assert __version__ == "0.3.0"
    with pytest.raises(SystemExit):
        main(["--version"])
    assert capsys.readouterr().out.strip() == "pixelbudget 0.3.0"
