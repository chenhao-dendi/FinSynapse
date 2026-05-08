from __future__ import annotations

from pathlib import Path

from scripts.check_data_source_catalog import (
    KNOWN_GAP_STATUSES,
    catalog_indicators,
    fixture_indicators,
    load_catalog,
    validate_catalog,
    weighted_indicators,
)

from finsynapse.transform.health_check import PLAUSIBLE_BOUNDS

CATALOG_PATH = Path("config/data_sources.yaml")
WEIGHTS_PATH = Path("config/weights.yaml")
FIXTURE_MACRO_PATH = Path("tests/fixtures/eval_silver_2026Q1/macro_daily.parquet")


def test_data_source_catalog_validates():
    assert validate_catalog(CATALOG_PATH, WEIGHTS_PATH) == []


def test_catalog_covers_weighted_and_collected_only_indicators():
    catalog = load_catalog(CATALOG_PATH)
    indicators = catalog_indicators(catalog)

    assert weighted_indicators(WEIGHTS_PATH).issubset(indicators)
    for indicator in {
        "us3m_yield",
        "us_t10y3m",
        "us_baa10y_spread",
        "us_on_rrp",
        "us_reserve_balances",
        "us_effr",
        "us_sofr",
        "us_cape_shiller",
        "us_tr_cape_shiller",
        "us_shiller_real_price",
        "us_shiller_real_dividend",
        "us_shiller_real_earnings",
        "us_tga_balance",
        "us_tga_deposits",
        "us_tga_withdrawals",
        "hk_aggregate_balance",
        "hk_monetary_base",
        "hk_hsi_pe",
        "hk_hsi_dividend_yield",
    }:
        assert indicator in indicators


def test_weighted_and_collected_only_indicators_have_health_bounds():
    catalog = load_catalog(CATALOG_PATH)

    for source in catalog["sources"].values():
        for indicator, meta in source.get("indicators", {}).items():
            if meta["usage"] in {"weighted", "collected_only"}:
                assert indicator in PLAUSIBLE_BOUNDS


def test_eval_fixture_macro_indicators_are_cataloged():
    catalog = load_catalog(CATALOG_PATH)
    assert fixture_indicators(FIXTURE_MACRO_PATH).issubset(catalog_indicators(catalog))


def test_pdf_archive_sources_are_manual_ingest_only():
    from finsynapse.cli import MANUAL_INGEST_SOURCES, SOURCES

    assert "hsi_monthly_valuation" in SOURCES
    assert "hsi_monthly_valuation" in MANUAL_INGEST_SOURCES


def test_catalog_tracks_known_data_gaps():
    catalog = load_catalog(CATALOG_PATH)
    gaps = catalog["known_gaps"]

    assert {
        "hk_native_valuation",
        "hsi_options_pcr",
        "ah_premium_history",
        "hk_vhsi_fixture_history",
        "us_hy_oas_full_history",
        "eval_fixture_warmup_history",
    }.issubset(gaps)
    assert all(gap["status"] in KNOWN_GAP_STATUSES for gap in gaps.values())
    assert gaps["hk_native_valuation"]["status"] == "source_ready"
    assert gaps["hk_vhsi_fixture_history"]["status"] == "source_ready"
    assert gaps["eval_fixture_warmup_history"]["status"] == "requires_fixture_rebuild"
