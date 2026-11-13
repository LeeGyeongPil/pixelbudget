"""Model table loading, validation and alias lookup."""

from __future__ import annotations

import difflib
import functools
import json
import os
import re
from importlib import resources
from pathlib import Path

from .errors import ModelTableError, UnknownModelError, UnsupportedDetailError
from .types import ModelSpec

MODELS_ENV = "PIXELBUDGET_MODELS"
_override: str | None = None  # set by the CLI's --models-file for the duration of one command

_METHODS = {"patch", "tile", "fixed"}
_CONFIDENCE = {"documented", "measured", "approx"}
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate(raw: dict, origin: str = "builtin") -> ModelSpec:
    for key in ("name", "provider", "method", "family", "detail_rules", "default_detail",
                "source_url", "checked", "confidence"):
        if key not in raw:
            raise ModelTableError(key="model_table_missing", name=raw.get("name"), field=key)
    if raw["method"] not in _METHODS:
        raise ModelTableError(key="model_table_method", name=raw["name"], method=raw["method"])
    if raw["confidence"] not in _CONFIDENCE:
        raise ModelTableError(key="model_table_confidence", name=raw["name"], confidence=raw["confidence"])
    if not str(raw["source_url"]).startswith("http"):
        raise ModelTableError(key="model_table_source", name=raw["name"])
    if not _DATE.match(str(raw["checked"])):
        raise ModelTableError(key="model_table_checked", name=raw["name"])
    if raw["default_detail"] not in raw["detail_rules"]:
        raise ModelTableError(key="model_table_default_detail", name=raw["name"])
    return ModelSpec(
        name=raw["name"], provider=raw["provider"], method=raw["method"], family=raw["family"],
        detail_rules=dict(raw["detail_rules"]), default_detail=raw["default_detail"],
        detail_aliases=dict(raw.get("detail_aliases", {})), aliases=tuple(raw.get("aliases", ())),
        source_url=raw["source_url"], checked=raw["checked"], confidence=raw["confidence"],
        notes=tuple(raw.get("notes", ())), known_mismatches=tuple(raw.get("known_mismatches", ())),
        origin=origin,
    )


def _user_rows(path: str) -> list[ModelSpec]:
    """Read and validate a user models file (same schema as the bundled table)."""
    try:
        # utf-8-sig accepts an optional BOM; non-UTF-8 bytes raise UnicodeDecodeError (a ValueError)
        text = Path(path).read_text(encoding="utf-8-sig")
        data = json.loads(text)
    except ValueError as exc:
        raise ModelTableError(key="model_table_json", path=path, reason=str(exc)) from exc
    if not isinstance(data, dict) or not isinstance(data.get("models"), list):
        raise ModelTableError(key="model_table_file", path=path)
    rows = []
    for raw in data["models"]:
        if not isinstance(raw, dict):
            raise ModelTableError(key="model_table_file", path=path)
        rows.append(_validate(raw, origin="user"))
    seen: set[str] = set()
    for spec in rows:
        if spec.name.lower() in seen:
            raise ModelTableError(key="model_table_duplicate", alias=spec.name)
        seen.add(spec.name.lower())
    return rows


def _models_path() -> str:
    """Active user file: --models-file (CLI) > PIXELBUDGET_MODELS > none (empty string)."""
    return _override or os.environ.get(MODELS_ENV, "")


def set_models_file(path: str | None) -> None:
    """Internal: CLI hook for --models-file (None clears it)."""
    global _override
    _override = path or None


def _load() -> tuple[tuple[ModelSpec, ...], dict[str, ModelSpec]]:
    return _load_path(_models_path())


@functools.lru_cache(maxsize=8)
def _load_path(path: str) -> tuple[tuple[ModelSpec, ...], dict[str, ModelSpec]]:
    text = resources.files("pixelbudget").joinpath("data/models.json").read_text(encoding="utf-8")
    rows = [_validate(r) for r in json.loads(text)["models"]]
    if path:
        for user in _user_rows(path):
            # same name (case-insensitive) replaces the whole bundled row, otherwise append
            for n, old in enumerate(rows):
                if old.name.lower() == user.name.lower():
                    rows[n] = user
                    break
            else:
                rows.append(user)
    specs = tuple(rows)
    index: dict[str, ModelSpec] = {}
    for spec in specs:
        for key in (spec.name, *spec.aliases):
            k = key.lower()
            if k in index:
                raise ModelTableError(key="model_table_duplicate", alias=key)
            index[k] = spec
    return specs, index


def list_models() -> list[ModelSpec]:
    """Return every row of the model table."""
    return list(_load()[0])


def get_model(name: str) -> ModelSpec:
    """Look a model up by name or alias (case-insensitive)."""
    index = _load()[1]
    spec = index.get(str(name).strip().lower())
    if spec is None:
        close = difflib.get_close_matches(str(name).lower(), list(index), n=3)
        # 비슷한 이름이 있으면 "혹시 이것?" 문구가 붙은 템플릿을 쓴다(문구는 locales/*.json).
        if close:
            raise UnknownModelError(key="unknown_model_suggest", name=name, suggestions=", ".join(close))
        raise UnknownModelError(name=name)
    return spec


def resolve_detail(spec: ModelSpec, detail: str | None) -> tuple[str, dict]:
    """Return (detail name, rule parameters) for ``detail`` (None -> model default)."""
    if detail is None:
        detail = "auto"
    key = detail.lower()
    if key in spec.detail_rules:
        return key, spec.detail_rules[key]
    if key in spec.detail_aliases:
        real = spec.detail_aliases[key]
        return real, spec.detail_rules[real]
    if detail == "auto" or key == "auto":
        return spec.default_detail, spec.detail_rules[spec.default_detail]
    supported = sorted(set(spec.detail_rules) | set(spec.detail_aliases))
    raise UnsupportedDetailError(model=spec.name, detail=detail, supported=", ".join(supported))
