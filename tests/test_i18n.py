"""AC-9: English/Korean UI, identical message keys and the language priority order."""

from __future__ import annotations

import json
from importlib import resources

import pytest

from pixelbudget.cli import main
from pixelbudget.i18n import resolve_lang


def _keys(lang):
    return set(json.loads(resources.files("pixelbudget").joinpath(f"locales/{lang}.json").read_text("utf-8")))


def test_key_sets_are_identical():
    assert _keys("en") == _keys("ko")


def test_every_warning_code_has_messages():
    from pixelbudget.types import WARNING_CODES

    assert {f"warn.{c}" for c in WARNING_CODES} <= _keys("en")


def test_priority_order():
    env = {"PIXELBUDGET_LANG": "en", "LC_ALL": "ko_KR.UTF-8", "LANG": "ko_KR.UTF-8"}
    assert resolve_lang("ko", env) == "ko"  # --lang wins
    assert resolve_lang(None, env) == "en"  # PIXELBUDGET_LANG beats the locale
    assert resolve_lang(None, {"LC_ALL": "ko_KR.UTF-8", "LC_MESSAGES": "en_US.UTF-8"}) == "ko"
    assert resolve_lang(None, {"LC_MESSAGES": "ko_KR.UTF-8", "LANG": "en_US.UTF-8"}) == "ko"
    assert resolve_lang(None, {"LANG": "ko_KR.UTF-8"}) == "ko"
    assert resolve_lang(None, {"LC_ALL": "C", "LANG": "ko_KR.UTF-8"}) == "en"
    assert resolve_lang(None, {"LANG": "fr_FR.UTF-8"}) == "en"
    assert resolve_lang(None, {}) == "en"


@pytest.fixture
def shots(make_image, tmp_path):
    make_image("shots/a.png", (1920, 1080))
    return str(tmp_path / "shots")


def test_help_models_and_report_switch_language(shots, capsys):
    for lang, header, desc in (("ko", "모델", "비전 LLM"), ("en", "Model", "vision LLM")):
        with pytest.raises(SystemExit):
            main(["--lang", lang, "--help"])
        assert desc in capsys.readouterr().out
        assert main(["--lang", lang, "models"]) == 0
        assert header in capsys.readouterr().out
        assert main(["--lang", lang, "report", shots, "--model", "claude-standard"]) == 0
        out = capsys.readouterr().out
        assert header in out
        assert ("서버가 이 이미지를 먼저 줄입니다" if lang == "ko" else "The server will downscale") in out


def test_environment_variable_selects_language(monkeypatch, capsys):
    monkeypatch.setenv("PIXELBUDGET_LANG", "ko")
    assert main(["models"]) == 0
    assert "모델" in capsys.readouterr().out
    monkeypatch.setenv("LANG", "ko_KR.UTF-8")
    monkeypatch.setenv("PIXELBUDGET_LANG", "en")
    assert main(["models"]) == 0
    assert "Model" in capsys.readouterr().out
    assert main(["--lang", "ko", "models"]) == 0
    assert "모델" in capsys.readouterr().out


def test_non_korean_locale_is_english(monkeypatch, capsys):
    monkeypatch.setenv("LANG", "de_DE.UTF-8")
    main(["models"])
    assert "Provider" in capsys.readouterr().out
