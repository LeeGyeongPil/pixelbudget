"""AC-2: official documentation example values, pinned (see fixtures/doc_examples.json)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pixelbudget import estimate

CASES = json.loads((Path(__file__).parent / "fixtures" / "doc_examples.json").read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_doc_example(case):
    assert case["source_url"].startswith("https://"), "every case needs a source URL"
    assert case["checked"] == "2026-11-11"
    est = estimate(tuple(case["size"]), case["model"], detail=case["detail"])
    if case["sent"] is not None:
        assert est.sent_size == tuple(case["sent"])
    if case["tokens"] is not None:
        assert est.tokens == case["tokens"]


def test_all_cases_have_sources():
    assert len(CASES) >= 16
    assert all(c["source_url"] for c in CASES)


def test_openai_patch_documented_values():
    # 1024x1024 -> 32x32 = 1024 patches, x1.2 multiplier, rounded up.
    est = estimate((1024, 1024), "gpt-5.5", detail="high")
    assert est.tokens == 1229
    assert est.confidence == "documented"
