"""Singular nouns in English summary lines; Korean output unchanged."""

from __future__ import annotations

from pixelbudget.cli import main


def _summary(capsys, argv):
    assert main(argv) == 0
    return capsys.readouterr().out.strip().splitlines()


def test_en_report_one_row(tmp_path, make_image, capsys):
    make_image("one/a.png", (300, 200))
    out = _summary(capsys, ["--lang", "en", "report", str(tmp_path / "one"), "--model", "gpt-4o"])
    assert out[-1] == "1 row, 0 over budget, 0 skipped"


def test_en_report_two_rows_plural(tmp_path, make_image, capsys):
    make_image("two/a.png", (300, 200))
    out = _summary(capsys, ["--lang", "en", "report", str(tmp_path / "two"),
                            "--model", "gpt-4o", "--model", "claude-standard"])
    assert out[-1] == "2 rows, 0 over budget, 0 skipped"


def test_ko_report_one_row_unchanged(tmp_path, make_image, capsys):
    make_image("one/a.png", (300, 200))
    out = _summary(capsys, ["--lang", "ko", "report", str(tmp_path / "one"), "--model", "gpt-4o"])
    assert out[-1] == "1행, 예산 초과 0행, 건너뜀 0개"


def test_en_slice_one_piece(tmp_path, make_image, capsys):
    p = make_image("s.png", (300, 200))
    out = _summary(capsys, ["--lang", "en", "slice", str(p), "--model", "gpt-4o"])
    assert out[0].startswith("1 piece of up to")
