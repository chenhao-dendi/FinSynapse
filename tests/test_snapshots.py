"""Snapshot tests for API outputs and brief template.

Uses syrupy to detect drift in:
  - temperature_latest.json structure
  - divergence_latest.json structure
  - brief deterministic template output

Snapshots are stored in tests/__snapshots__/ and committed to git.
Update with: uv run pytest tests/test_snapshots.py --snapshot-update
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from finsynapse.report.facts import FactPack, _zone, _zone_emoji, assemble_facts
from finsynapse.report.llm import LLMResult
from finsynapse.report.markdown import _template_narrative, render_markdown

FIXTURE_DIR = Path("tests/fixtures/eval_silver_2026Q1")


@pytest.fixture
def fixture_temp_df():
    """Load temperature from the P0a silver fixture."""
    df = pd.read_parquet(FIXTURE_DIR / "temperature_daily.parquet")
    df["date"] = pd.to_datetime(df["date"])
    return df


@pytest.fixture
def fixture_macro_df():
    """Load macro from the P0a silver fixture."""
    return pd.read_parquet(FIXTURE_DIR / "macro_daily.parquet")


def test_temperature_latest_snapshot(snapshot, fixture_temp_df):
    """Snapshot temperature_latest.json structure from fixture data."""
    from finsynapse.dashboard.api import _build_temperature_latest
    from finsynapse.dashboard.data import DashboardData

    empty_div = pd.DataFrame(columns=["date", "pair_name", "strength"])
    empty_health = pd.DataFrame(columns=["date", "indicator", "check", "status"])
    empty_pct = pd.DataFrame(columns=["date", "indicator", "value", "pct_5y", "pct_10y"])

    data = DashboardData(
        temperature=fixture_temp_df,
        macro=fixture_macro_df,
        percentile=empty_pct,
        divergence=empty_div,
        health=empty_health,
        silver_dir=FIXTURE_DIR,
    )

    result = _build_temperature_latest(data)
    # Normalize volatile fields for reproducible snapshots
    result["asof"] = "FIXTURE"
    result["raw_temperature_asof"] = "FIXTURE"
    if "generated_at_utc" in result:
        result["generated_at_utc"] = "FIXTURE"
    for mkt in result.get("market_asof", {}):
        if result["market_asof"][mkt]:
            result["market_asof"][mkt] = "FIXTURE"
    for mkt in result.get("latest_complete_date", {}):
        if result["latest_complete_date"][mkt]:
            result["latest_complete_date"][mkt] = "FIXTURE"
    for mkt_data in result.get("markets", {}).values():
        if mkt_data.get("asof"):
            mkt_data["asof"] = "FIXTURE"
        if mkt_data.get("latest_complete_date"):
            mkt_data["latest_complete_date"] = "FIXTURE"

    assert snapshot == json.dumps(result, indent=2, ensure_ascii=False)


def test_divergence_latest_snapshot(snapshot, fixture_temp_df):
    """Snapshot divergence_latest.json structure from fixture data."""
    from finsynapse.dashboard.api import _build_divergence_latest
    from finsynapse.dashboard.data import DashboardData

    empty_macro = pd.DataFrame(columns=["date", "indicator", "value", "source"])
    empty_pct = pd.DataFrame(columns=["date", "indicator", "value", "pct_5y", "pct_10y"])
    empty_health = pd.DataFrame(columns=["date", "indicator", "check", "status"])
    empty_div = pd.DataFrame(columns=["date", "pair_name", "strength", "is_divergent", "description"])

    data = DashboardData(
        temperature=fixture_temp_df,
        macro=empty_macro,
        percentile=empty_pct,
        divergence=empty_div,
        health=empty_health,
        silver_dir=FIXTURE_DIR,
    )

    result = _build_divergence_latest(data, window_days=90)
    assert isinstance(result, dict)
    assert "signals" in result


def test_brief_template_snapshot(snapshot, fixture_temp_df, fixture_macro_df):
    """Snapshot the deterministic brief template output from fixture data."""
    from finsynapse.dashboard.data import DashboardData

    empty_pct = pd.DataFrame(columns=["date", "indicator", "value", "pct_5y", "pct_10y"])
    empty_div = pd.DataFrame(columns=["date", "pair_name", "strength", "is_divergent", "description"])
    empty_health = pd.DataFrame(columns=["date", "indicator", "check", "status"])

    data = DashboardData(
        temperature=fixture_temp_df,
        macro=fixture_macro_df,
        percentile=empty_pct,
        divergence=empty_div,
        health=empty_health,
        silver_dir=FIXTURE_DIR,
    )

    latest = data.latest_per_market()
    asof = max(pd.to_datetime(row["date"]) for row in latest.values()).date().isoformat()

    facts = FactPack(asof=asof)
    for mkt in ("cn", "hk", "us"):
        if mkt not in latest:
            continue
        row = latest[mkt]
        facts.markets[mkt] = {
            "date": pd.to_datetime(row["date"]).date().isoformat(),
            "overall": float(row["overall"]) if not pd.isna(row.get("overall")) else None,
            "overall_zone": _zone(row.get("overall")),
            "valuation": None if pd.isna(row.get("valuation")) else float(row["valuation"]),
            "sentiment": None if pd.isna(row.get("sentiment")) else float(row["sentiment"]),
            "liquidity": None if pd.isna(row.get("liquidity")) else float(row["liquidity"]),
            "overall_change_1w": (
                None if pd.isna(row.get("overall_change_1w")) else float(row["overall_change_1w"])
            ),
            "valuation_contribution_1w": (
                None if pd.isna(row.get("valuation_contribution_1w"))
                else float(row["valuation_contribution_1w"])
            ),
            "sentiment_contribution_1w": (
                None if pd.isna(row.get("sentiment_contribution_1w"))
                else float(row["sentiment_contribution_1w"])
            ),
            "liquidity_contribution_1w": (
                None if pd.isna(row.get("liquidity_contribution_1w"))
                else float(row["liquidity_contribution_1w"])
            ),
            "data_quality": str(row.get("data_quality", "ok")),
        }

    narrative = _template_narrative(facts)
    llm_result = LLMResult(provider="template", model=None, text=None)
    md = render_markdown(facts, narrative, llm_result)
    assert snapshot == md
