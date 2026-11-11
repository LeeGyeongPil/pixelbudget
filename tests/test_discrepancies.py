"""AC-3: documentation mismatches and approximations are reported, not hidden."""

from __future__ import annotations

import json
from pathlib import Path

from pixelbudget import estimate, list_models
from pixelbudget.cli import main

ROOT = Path(__file__).resolve().parent.parent


def test_claude_2000x1500_follows_reference_code_and_flags_table_mismatch():
    est = estimate((2000, 1500), "claude-standard")
    assert est.sent_size == (1270, 952)  # docs table says 1269x952; reference code says 1270x952
    assert est.tokens == 1564
    assert "docs_table_mismatch" in est.warnings
    assert any(n.startswith("docs_table_mismatch") and "1269x952" in n for n in est.notes)


def test_other_sizes_do_not_carry_the_mismatch_note():
    assert "docs_table_mismatch" not in estimate((1920, 1080), "claude-standard").warnings


def test_openai_patch_over_budget_is_approx():
    # 2048x2048 = 4096 patches > the 2500-patch budget of gpt-5.5 high -> proportional shrink.
    est = estimate((2048, 2048), "gpt-5.5", detail="high")
    assert est.confidence == "approx"
    assert "approx_rounding" in est.warnings
    assert est.server_downscaled


def test_openai_patch_within_budget_is_documented():
    # 1920x1080 is 60x34 = 2040 patches: already within 2500, so no approximation is involved.
    est = estimate((1920, 1080), "gpt-5.5", detail="high")
    assert (est.sent_size, est.tokens, est.confidence) == ((1920, 1080), 2448, "documented")
    assert estimate((1024, 1024), "gpt-5.5", detail="high").confidence == "documented"


def test_gemini2_is_approx():
    est = estimate((300, 300), "gemini-2")
    assert est.confidence == "approx" and "approx_rule" in est.warnings


def test_models_json_rows_have_provenance(capsys):
    assert main(["models", "--format", "json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == len(list_models()) >= 15
    for row in rows:
        assert row["source_url"].startswith("http")
        assert row["checked"] == "2026-11-11"
        assert row["confidence"] in {"documented", "measured", "approx"}


def test_model_table_doc_mentions_both_items():
    text = (ROOT / "docs" / "model-table.md").read_text(encoding="utf-8")
    assert "1269x952" in text and "1270x952" in text
    assert "approx_rounding" in text
