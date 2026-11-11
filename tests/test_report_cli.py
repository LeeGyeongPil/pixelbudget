"""AC-7: folder report, JSON output and the CI exit code; measuring never decodes pixels."""

from __future__ import annotations

import json

import pytest
from PIL import Image

from pixelbudget import report
from pixelbudget.cli import main


@pytest.fixture
def folder(tmp_path, make_image):
    make_image("shots/small.png", (300, 200))
    make_image("shots/hd.png", (1920, 1080))
    make_image("shots/tall.png", (1170, 9000))
    (tmp_path / "shots" / "notes.txt").write_text("not an image")
    return tmp_path / "shots"


def _no_decode(monkeypatch):
    def boom(self, *a, **k):
        raise AssertionError("pixels were decoded while measuring")

    monkeypatch.setattr(Image.Image, "load", boom)


def test_report_json_rows_and_exit_code(folder, capsys, monkeypatch):
    _no_decode(monkeypatch)
    argv = ["report", str(folder), "--model", "claude-standard", "--model", "gpt-4o",
            "--format", "json", "--max-tokens", "1500"]
    code = main(argv)
    data = json.loads(capsys.readouterr().out)
    rows = data["rows"]
    assert len(rows) == 6
    assert {r["path"].rsplit("/", 1)[-1] for r in rows} == {"small.png", "hd.png", "tall.png"}
    for key in ("path", "tokens", "sent_size", "server_downscaled", "wasted_pixels", "over_budget"):
        assert all(key in r for r in rows)
    hd = next(r for r in rows if r["path"].endswith("hd.png") and r["model"] == "claude-standard")
    assert hd["sent_size"] == [1456, 819] and hd["server_downscaled"] and hd["tokens"] == 1560
    assert hd["wasted_pixels"] == 1920 * 1080 - 1456 * 819
    assert hd["over_budget"] is True
    assert code == 1


def test_exit_zero_when_nothing_is_over(folder, capsys):
    code = main(["report", str(folder), "--model", "claude-standard", "--format", "json", "--max-tokens", "9999"])
    assert code == 0
    assert json.loads(capsys.readouterr().out)["summary"]["over_budget"] == 0


def test_text_table_and_cost_column(folder, capsys):
    code = main(["--lang", "en", "report", str(folder), "--model", "claude-standard",
                 "--price", "claude-standard=3", "--max-tokens", "1500"])
    out = capsys.readouterr().out
    assert code == 1
    assert "Cost USD" in out and "Over budget" in out and "notes.txt" not in out


def test_library_report_skips_non_images_and_unreadable(tmp_path, make_image):
    make_image("a.png", (100, 100))
    (tmp_path / "b.png").write_text("this is not a png")
    result = report([tmp_path], ["claude-standard"])
    assert [r.path.rsplit("/", 1)[-1] for r in result] == ["a.png"]


def test_unknown_model_message(capsys):
    code = main(["estimate", "x.png", "--model", "claude-standrad"])
    assert code == 2
    assert "Did you mean" in capsys.readouterr().err


def test_fit_and_slice_cli_write_files(make_image, tmp_path, capsys):
    path = make_image("tall.png", (1170, 9000))
    assert main(["fit", path, "--model", "claude-standard", "--budget", "800"]) == 0
    assert (tmp_path / "tall.fit.png").exists()
    assert Image.open(tmp_path / "tall.fit.png").size[1] <= 1568
    assert main(["slice", path, "--model", "claude-standard"]) == 0
    assert len(list((tmp_path / "tall-slices").iterdir())) == 10
    assert main(["slice", path, "--model", "claude-standard", "--dry-run", "--out-dir", str(tmp_path / "x")]) == 0
    assert not (tmp_path / "x").exists()


def test_demo_runs_and_writes_images(tmp_path, capsys):
    out = tmp_path / "demo"
    assert main(["--lang", "en", "demo", "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "synthetic practice data" in text and "14364" in text
    assert sorted(p.name for p in out.iterdir()) == ["compare.png", "fit.png", "slice-01.png"]
