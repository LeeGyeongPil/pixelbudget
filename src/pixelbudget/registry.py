"""Model table loading, validation and alias lookup."""

from __future__ import annotations

import difflib
import functools
import json
import re
from importlib import resources

from .errors import ModelTableError, UnknownModelError, UnsupportedDetailError
from .types import ModelSpec

_METHODS = {"patch", "tile", "fixed"}
_CONFIDENCE = {"documented", "measured", "approx"}
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate(raw: dict) -> ModelSpec:
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
    )


@functools.lru_cache(maxsize=1)
def _load() -> tuple[tuple[ModelSpec, ...], dict[str, ModelSpec]]:
    text = resources.files("pixelbudget").joinpath("data/models.json").read_text(encoding="utf-8")
    specs = tuple(_validate(r) for r in json.loads(text)["models"])
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
