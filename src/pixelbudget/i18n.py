"""CLI language selection and message lookup (English / Korean)."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from importlib import resources
from typing import Mapping

LANGS = ("en", "ko")
ENV_VAR = "PIXELBUDGET_LANG"


def _normalise(value: str | None) -> str | None:
    if not value:
        return None
    return "ko" if value.strip().lower().startswith("ko") else "en"


def resolve_lang(cli_value: str | None = None, env: Mapping[str, str] | None = None) -> str:
    """Pick the language: ``--lang`` > PIXELBUDGET_LANG > LC_ALL > LC_MESSAGES > LANG; else English."""
    env = os.environ if env is None else env
    if cli_value:
        return _normalise(cli_value) or "en"
    for key in (ENV_VAR, "LC_ALL", "LC_MESSAGES", "LANG"):
        found = _normalise(env.get(key))
        if found:
            return found
    return "en"


@lru_cache(maxsize=None)
def messages(lang: str) -> dict[str, str]:
    text = resources.files("pixelbudget").joinpath(f"locales/{lang}.json").read_text(encoding="utf-8")
    return json.loads(text)


def t(lang: str, key: str, **kwargs: object) -> str:
    """Translate ``key``; falls back to English, then to the key itself."""
    table = messages(lang)
    template = table.get(key) or messages("en").get(key) or key
    return template.format(**kwargs) if kwargs else template
