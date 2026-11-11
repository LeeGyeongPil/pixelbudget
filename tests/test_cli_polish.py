"""Round-2 fixes: fully translated --help/usage errors, display-width table alignment, --strict, str arguments."""

from __future__ import annotations

import unicodedata

import pytest

from pixelbudget import report
from pixelbudget.cli import main

ENGLISH_ARGPARSE = ("show this help message", "positional arguments", "usage:", "options:",
                    "show program's version", "the following arguments are required", "invalid choice")


def _width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in text)


@pytest.mark.parametrize("argv", [["--help"], ["report", "--help"], ["estimate", "--help"], ["fit", "--help"],
                                  ["slice", "--help"], ["models", "--help"], ["demo", "--help"]])
def test_korean_help_has_no_english_argparse_text(argv, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--lang", "ko", *argv])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "사용법:" in out and "도움말을 보여 주고 종료합니다" in out
    assert not [s for s in ENGLISH_ARGPARSE if s in out]


def test_english_help_still_english(capsys):
    with pytest.raises(SystemExit):
        main(["--lang", "en", "--help"])
    out = capsys.readouterr().out
    assert "usage:" in out and "positional arguments" in out and "Show this help message" in out


@pytest.mark.parametrize("argv, expected", [
    (["estimate"], "다음 인자가 필요합니다"),
    (["bogus"], "잘못된 선택값"),
    (["fit", "x.png", "--model", "a", "--budget", "abc"], "잘못된 int 값"),
    (["fit", "x.png", "--model"], "값이 하나 필요합니다"),
    (["models", "--nope"], "인식할 수 없는 인자"),
])
def test_korean_usage_errors(argv, expected, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--lang", "ko", *argv])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert expected in err and "사용법:" in err
    assert not [s for s in ENGLISH_ARGPARSE if s in err]


def test_korean_report_table_aligns_by_display_width(make_image, tmp_path, capsys):
    make_image("shots/a.png", (1920, 1080))
    make_image("shots/b.png", (300, 200))
    code = main(["--lang", "ko", "report", str(tmp_path / "shots"), "--model", "claude-standard", "--model", "gpt-4o",
                 "--max-tokens", "1500"])
    out = capsys.readouterr().out
    assert code == 1
    lines = out.splitlines()
    rule_idx = next(i for i, ln in enumerate(lines) if ln.startswith("---"))
    header, rule = lines[rule_idx - 1], lines[rule_idx]
    rows = lines[rule_idx + 1: rule_idx + 5]
    # column starts come from the dashed rule (ASCII only, so len == display width)
    starts, pos = [], 0
    for chunk in rule.split("  "):
        starts.append(pos)
        pos += len(chunk) + 2
    for row in [header, *rows]:
        for start in starts:
            width = 0
            for ch in row:
                if width >= start:
                    break
                width += _width(ch)
            assert width == start, f"misaligned at column {start}: {row!r}"
            # the cell must start at a non-space character right after the two-space gap
            tail = row
            consumed = 0
            for i, ch in enumerate(row):
                if consumed >= start:
                    tail = row[i:]
                    break
                consumed += _width(ch)
            assert start == 0 or (tail and not tail[0].isspace()), f"gap mismatch at {start}: {row!r}"
    assert _width(header.rstrip()) <= _width(rule)


def test_table_width_helper_counts_hangul_as_two():
    from pixelbudget.cli import _table, _width as cli_width

    assert cli_width("모델") == 4 and cli_width("abc") == 3
    lines = _table(["경로", "x"], [["a", "예"], ["아니오", "y"]]).splitlines()
    # first column is padded to the display width of the widest cell (아니오 = 6) plus the 2-space gap
    for line, first in zip(lines, ["경로", "-" * 6, "a", "아니오"]):
        assert line.startswith(first + " " * (6 - cli_width(first) + 2)) or line == first
    assert lines[1] == "-" * 6 + "  " + "-" * 2


def test_unreadable_named_file_is_reported_and_strict_fails(tmp_path, capsys):
    bad = tmp_path / "bad.png"
    bad.write_text("not an image")
    argv = ["--lang", "en", "report", str(bad), "--model", "claude-standard", "--max-tokens", "1500"]
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "No image files found" not in out and "No readable images found" in out and "bad.png" in out
    assert main([*argv, "--strict"]) == 1


def test_library_accepts_a_lone_string(tmp_path, make_image):
    make_image("a.png", (100, 100))
    rows = report(str(tmp_path), "claude-standard")
    assert [r.model for r in rows] == ["claude-standard"]
    assert len(report([str(tmp_path)], ["claude-standard"])) == 1
    assert len(report(tmp_path, "claude-standard")) == 1


def test_library_rejects_non_iterables():
    with pytest.raises(TypeError, match="paths must be"):
        report(5, ["claude-standard"])
