"""AC-10: offline, a single runtime dependency, no local-user path strings."""

from __future__ import annotations

import socket
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = ("/" + "Users/", "/" + "home/")  # split so this file does not match itself


def test_only_pillow_is_a_runtime_dependency():
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text())
    deps = meta["project"]["dependencies"]
    assert len(deps) == 1 and deps[0].lower().startswith("pillow")


def test_network_is_blocked_in_tests():
    with pytest.raises(AssertionError, match="network"):
        socket.socket().connect(("127.0.0.1", 9))


def test_no_local_user_paths_in_repo_text_files():
    skip_dirs = {".git", ".venv", "__pycache__", ".pytest_cache", "dist", "build"}
    text_suffixes = {".py", ".md", ".json", ".toml", ".yml", ".yaml", ".txt", ""}
    bad = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or skip_dirs & set(path.relative_to(ROOT).parts):
            continue
        if path.suffix not in text_suffixes or path.name == "uv.lock":
            continue
        if path.resolve() == Path(__file__).resolve():
            continue  # this file names the forbidden strings
        content = path.read_text(encoding="utf-8", errors="ignore")
        bad += [str(path.relative_to(ROOT)) for needle in FORBIDDEN if needle in content]
    assert bad == []
