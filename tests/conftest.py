"""Shared fixtures: no network, no API keys, synthetic images built with Pillow."""

from __future__ import annotations

import socket

import pytest
from PIL import Image

API_KEY_VARS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY")


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """Any socket connection attempt fails the test; API key variables are removed."""

    def blocked(*args, **kwargs):
        raise AssertionError("network access attempted during an offline test")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    for var in API_KEY_VARS:
        monkeypatch.delenv(var, raising=False)
    for var in ("PIXELBUDGET_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def make_image(tmp_path):
    """Factory: ``make_image("name.png", (w, h))`` writes a synthetic image and returns its path."""

    def factory(name: str, size: tuple[int, int], **save_kwargs) -> str:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", size, "white").save(path, **save_kwargs)
        return str(path)

    return factory
