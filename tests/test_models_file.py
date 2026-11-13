"""--models-file / PIXELBUDGET_MODELS: user rows replace or extend the bundled table."""

from __future__ import annotations

import copy
import json

import pytest

from pixelbudget import estimate, get_model, list_models
from pixelbudget.cli import main
from pixelbudget.errors import ModelTableError
from pixelbudget.registry import MODELS_ENV


@pytest.fixture(autouse=True)
def _no_models_env(monkeypatch):
    monkeypatch.delenv(MODELS_ENV, raising=False)


def _row(name="my-model", **over):
    row = {
        "name": name, "provider": "me", "method": "patch", "family": "anthropic",
        "detail_rules": {"standard": {"patch": 28, "max_edge": 1568, "max_tokens": 1568}},
        "default_detail": "standard", "source_url": "https://example.com/docs",
        "checked": "2026-11-13", "confidence": "measured",
    }
    row.update(over)
    return row


def _write(tmp_path, models, name="models.json"):
    path = tmp_path / name
    path.write_text(json.dumps({"models": models}), encoding="utf-8")
    return str(path)


def _bundled_row():
    """A bundled row as a user row (same name, different source)."""
    spec = list_models()[0]
    return spec, spec.name


def test_same_name_overrides_row(tmp_path, monkeypatch):
    spec, name = _bundled_row()
    base = copy.deepcopy(spec.detail_rules)
    row = _row(name=name.upper(), method=spec.method, family=spec.family,
               detail_rules=base, default_detail=spec.default_detail,
               source_url="https://example.com/mine", confidence="approx")
    monkeypatch.setenv(MODELS_ENV, _write(tmp_path, [row]))
    got = get_model(name)
    assert got.origin == "user" and got.source_url == "https://example.com/mine"
    assert got.aliases == ()  # the whole row is replaced, aliases included
    assert len(list_models()) == len(_builtin_count())
    est = estimate((800, 600), name)
    assert "user_model_row" in est.warnings
    assert any(n.startswith("user_model_row:") for n in est.notes)
    assert sum(1 for s in list_models() if s.origin == "user") == 1


def _builtin_count():
    import os
    saved = os.environ.pop(MODELS_ENV)
    try:
        return list_models()
    finally:
        os.environ[MODELS_ENV] = saved


def test_new_name_is_appended_and_estimable(tmp_path, monkeypatch):
    before = len(list_models())
    monkeypatch.setenv(MODELS_ENV, _write(tmp_path, [_row()]))
    specs = list_models()
    assert len(specs) == before + 1 and specs[-1].name == "my-model"
    est = estimate((800, 600), "my-model")
    assert est.tokens > 0 and "user_model_row" in est.warnings
    assert specs[-1].as_dict()["origin"] == "user"


def test_without_file_matches_bundled_output(capsys):
    assert main(["--lang", "en", "models"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split()[-1] == "Origin"
    assert all(line.split()[-1] == "builtin" for line in lines[2:] if line.strip())
    assert all(s.origin == "builtin" for s in list_models())
    assert "user_model_row" not in estimate((800, 600), list_models()[0].name).warnings


def test_env_change_is_picked_up_by_next_call(tmp_path, monkeypatch):
    before = len(list_models())
    monkeypatch.setenv(MODELS_ENV, _write(tmp_path, [_row()]))
    assert len(list_models()) == before + 1
    monkeypatch.delenv(MODELS_ENV)
    assert len(list_models()) == before


def test_flag_beats_env(tmp_path, monkeypatch, capsys):
    env_file = _write(tmp_path, [_row("from-env")], "env.json")
    flag_file = _write(tmp_path, [_row("from-flag")], "flag.json")
    monkeypatch.setenv(MODELS_ENV, env_file)
    assert main(["--models-file", flag_file, "models"]) == 0
    out = capsys.readouterr().out
    assert "from-flag" in out and "from-env" not in out
    # the flag does not leak into later calls
    assert [s.name for s in list_models()][-1] == "from-env"
    assert main(["models"]) == 0
    assert "from-env" in capsys.readouterr().out


def test_cli_json_has_origin(tmp_path, capsys):
    path = _write(tmp_path, [_row()])
    assert main(["--models-file", path, "models", "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data[-1]["origin"] == "user" and data[0]["origin"] == "builtin"


@pytest.mark.parametrize("lang, expected", [
    ("en", "not valid JSON"),
    ("ko", "올바른 JSON 이 아닙니다"),
])
def test_invalid_json_exit_2(tmp_path, capsys, lang, expected):
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    assert main(["--lang", lang, "--models-file", str(bad), "models"]) == 2
    err = capsys.readouterr().err
    assert expected in err and str(bad) in err


@pytest.mark.parametrize("lang, expected", [("en", "not valid JSON"), ("ko", "올바른 JSON 이 아닙니다")])
def test_non_utf8_file_exit_2(tmp_path, capsys, lang, expected):
    bad = tmp_path / "utf16.json"
    bad.write_text(json.dumps({"models": [_row()]}), encoding="utf-16")
    assert main(["--lang", lang, "--models-file", str(bad), "models"]) == 2
    err = capsys.readouterr().err
    assert expected in err and "Traceback" not in err


def test_utf8_bom_file_loads(tmp_path):
    path = tmp_path / "bom.json"
    path.write_text(json.dumps({"models": [_row("bom-model")]}), encoding="utf-8-sig")
    assert main(["--models-file", str(path), "models"]) == 0


@pytest.mark.parametrize("content", ['[]', '{"models": 3}', '{"rows": []}', '{"models": [1]}'])
@pytest.mark.parametrize("lang, expected", [("en", "expected an object"), ("ko", "객체여야 합니다")])
def test_wrong_shape_exit_2(tmp_path, capsys, content, lang, expected):
    bad = tmp_path / "shape.json"
    bad.write_text(content, encoding="utf-8")
    assert main(["--lang", lang, "--models-file", str(bad), "models"]) == 2
    assert expected in capsys.readouterr().err


def test_missing_required_field_exit_2(tmp_path, capsys):
    row = _row()
    del row["source_url"]
    path = _write(tmp_path, [row])
    assert main(["--lang", "en", "--models-file", path, "models"]) == 2
    assert "source_url" in capsys.readouterr().err
    assert main(["--lang", "ko", "--models-file", path, "models"]) == 2
    assert capsys.readouterr().err


def test_missing_file_exit_2(tmp_path, capsys):
    assert main(["--models-file", str(tmp_path / "nope.json"), "models"]) == 2
    assert "nope.json" in capsys.readouterr().err


def test_library_raises_model_table_error(tmp_path, monkeypatch):
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    monkeypatch.setenv(MODELS_ENV, str(bad))
    with pytest.raises(ModelTableError, match="not valid JSON"):
        list_models()


def test_duplicate_alias_and_duplicate_name(tmp_path, monkeypatch):
    spec = list_models()[0]
    clash = _row(aliases=[spec.name])  # alias equals a bundled name
    monkeypatch.setenv(MODELS_ENV, _write(tmp_path, [clash], "a.json"))
    with pytest.raises(ModelTableError, match="duplicate"):
        list_models()
    twice = _write(tmp_path, [_row(), _row("MY-MODEL")], "b.json")
    monkeypatch.setenv(MODELS_ENV, twice)
    with pytest.raises(ModelTableError, match="duplicate"):
        list_models()
