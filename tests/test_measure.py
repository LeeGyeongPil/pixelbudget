"""AC-8: EXIF orientation, decompression-bomb handling and decode guards."""

from __future__ import annotations

import pytest
from PIL import Image

from pixelbudget import ImageTooLargeError, InvalidSizeError, estimate, fit, measure, report, slice_image
from pixelbudget.cli import main


def _exif_jpeg(tmp_path, orientation):
    path = tmp_path / f"o{orientation}.jpg"
    img = Image.new("RGB", (400, 300), "white")
    exif = Image.Exif()
    exif[0x0112] = orientation
    img.save(path, exif=exif)
    return str(path)


def test_exif_orientation_6_is_measured_as_300x400(tmp_path):
    assert measure(_exif_jpeg(tmp_path, 6)) == (300, 400)
    assert measure(_exif_jpeg(tmp_path, 1)) == (400, 300)
    assert estimate(_exif_jpeg(tmp_path, 8), "claude-standard").original_size == (300, 400)


def test_exif_rotation_applied_when_decoding(tmp_path):
    res = fit(_exif_jpeg(tmp_path, 6), "claude-standard", budget=100)
    assert res.image.size[0] < res.image.size[1]


def test_tuple_and_image_inputs():
    assert measure((12, 34)) == (12, 34)
    assert measure(Image.new("RGB", (5, 6))) == (5, 6)
    with pytest.raises(InvalidSizeError):
        measure((0, 5))


def test_big_images_are_measured_from_the_header(make_image, monkeypatch):
    path = make_image("big.png", (300, 300))
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)  # 300x300 is far beyond 2x this limit
    est = estimate(path, "claude-standard")
    assert est.original_size == (300, 300)
    assert "decompression_guard" in est.warnings
    rows = report([path], ["claude-standard"])
    assert "decompression_guard" in rows[0].warnings


def test_fit_and_slice_raise_with_max_pixels_hint(make_image, monkeypatch):
    path = make_image("big.png", (300, 300))
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    with pytest.raises(ImageTooLargeError, match="max_pixels"):
        fit(path, "claude-standard", budget=100)
    with pytest.raises(ImageTooLargeError, match="max_pixels"):
        slice_image(path, "claude-standard")
    assert fit(path, "claude-standard", budget=100, max_pixels=1_000_000).image.size[0] < 300
    assert len(slice_image(path, "gemini-3", max_pixels=1_000_000).images) >= 1


def test_cli_reports_too_large_as_error(make_image, monkeypatch, capsys):
    path = make_image("big.png", (300, 300))
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    assert main(["fit", path, "--model", "claude-standard", "--budget", "100"]) == 2
    assert "max_pixels" in capsys.readouterr().err
    assert main(["fit", path, "--model", "claude-standard", "--budget", "100", "--max-pixels", "1000000"]) == 0
