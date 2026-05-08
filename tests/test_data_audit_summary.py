from __future__ import annotations

from pathlib import Path

from scripts.summarize_data_audit import build_summary

CATALOG_PATH = Path("config/data_sources.yaml")
MANIFEST_PATH = Path("tests/fixtures/eval_silver_2026Q1/MANIFEST.json")


def test_data_audit_summary_includes_pr_relevant_evidence():
    summary = build_summary(CATALOG_PATH, MANIFEST_PATH)

    assert "## Data Audit Summary" in summary
    assert "Official public sources: 6" in summary
    assert "treasury_yield_curve" in summary
    assert "treasury_dts" in summary
    assert "hkma_monetary_base" in summary
    assert "hsi_monthly_valuation" in summary
    assert "us_t10y3m" in summary
    assert "us_baa10y_spread" in summary
    assert "us_on_rrp" in summary
    assert "us_reserve_balances" in summary
    assert "us_effr" in summary
    assert "us_sofr" in summary
    assert "us_tga_balance" in summary
    assert "hk_aggregate_balance" in summary
    assert "hk_hsi_pe" in summary
    assert "hk_hsi_dividend_yield" in summary
    assert "Pivot coverage: 25/25" in summary
    assert "Indicator pivot checks: 184/218" in summary
    assert "Missing required indicator-window checks: 34" in summary
    assert "Top fixture data gaps: hk_vhsi=8, us_hy_oas=7" in summary
    assert "Macro rows: 102,119 across 42 indicators" in summary
    assert "Percentile rows: 124,399" in summary
    assert "hk_native_valuation" in summary
    assert "hk_vhsi_fixture_history" in summary
    assert "us_hy_oas_full_history" in summary
    assert "eval_fixture_warmup_history" in summary
    assert "uv run python scripts/check_data_source_catalog.py" in summary
