from __future__ import annotations

from pathlib import Path

from scripts.compare_eval_fixtures import build_comparison, render_markdown

FIXTURE_DIR = Path("tests/fixtures/eval_silver_2026Q1")


def test_compare_eval_fixtures_baseline_to_itself_has_no_delta():
    comparison = build_comparison(FIXTURE_DIR, FIXTURE_DIR)
    report = render_markdown(comparison)

    assert "## Eval Fixture Candidate Comparison" in report
    assert "Macro rows: 110,523 -> 110,523 (+0)" in report
    assert "Indicator pivot checks: 184/218 -> 184/218 (+0)" in report
    assert "Missing required checks: 34 -> 34 (+0)" in report
    assert "`pivot_directional_rate`: 0.9200 -> 0.9200 (+0.0000, block, PASS)" in report
    assert "### Required Percentile Coverage Delta" in report
    assert "Resolved missing checks: none" in report
    assert "Newly missing checks: none" in report
    assert "### Pivot Changes" in report
    assert "- none" in report


def test_compare_eval_fixtures_lists_resolved_missing_percentile_checks(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    for name in ("macro_daily.parquet", "percentile_daily.parquet", "temperature_daily.parquet"):
        (candidate / name).write_bytes((FIXTURE_DIR / name).read_bytes())

    import pandas as pd

    pct = pd.read_parquet(candidate / "percentile_daily.parquet")
    mask = (pct["indicator"] == "dxy") & (pd.to_datetime(pct["date"]) == pd.Timestamp("2011-10-03"))
    pct.loc[mask, "pct_5y"] = 99.0
    pct.to_parquet(candidate / "percentile_daily.parquet", index=False)

    comparison = build_comparison(FIXTURE_DIR, candidate)
    report = render_markdown(comparison)

    assert "Indicator pivot checks: 184/218 -> 185/218 (+1)" in report
    assert "Missing required checks: 34 -> 33 (-1)" in report
    assert "Resolved missing checks: `dxy`=1" in report
    assert "Newly missing checks: none" in report
    assert "us 2011-10-03 `2011 US debt downgrade / Eurozone crisis low`: `dxy` pct_5y" in report


def test_compare_eval_fixtures_explains_changed_pivots(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    for name in ("macro_daily.parquet", "percentile_daily.parquet", "temperature_daily.parquet"):
        (candidate / name).write_bytes((FIXTURE_DIR / name).read_bytes())

    import pandas as pd

    temp = pd.read_parquet(candidate / "temperature_daily.parquet")
    mask = (temp["market"] == "hk") & (pd.to_datetime(temp["date"]) == pd.Timestamp("2024-10-10"))
    temp.loc[mask, ["overall", "valuation", "sentiment", "liquidity"]] = [17.5, 17.5, 54.2, 50.8]
    temp.to_parquet(candidate / "temperature_daily.parquet", index=False)

    comparison = build_comparison(FIXTURE_DIR, candidate)
    report = render_markdown(comparison)

    assert "hk 2024-10-10 `2024 9.24 policy-pivot surge`" in report
    assert "subtemps: overall=38.6, valuation=17.5, sentiment=89.0, liquidity=50.8" in report
    assert "`cn_south_5d` (pct_5y, dir +): 89.0 on 2024-10-10" in report
    assert "`hk_vhsi` (pct_5y, dir -): missing -> missing" in report
