from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from finsynapse.transform.divergence import compute_divergence
from finsynapse.transform.health_check import check
from finsynapse.transform.normalize import collect_bronze, derive_indicators
from finsynapse.transform.percentile import compute_percentiles
from finsynapse.transform.temperature import WeightsConfig, compute_temperature


def _build_macro(indicators: dict[str, list[float]], start="2010-01-04") -> pd.DataFrame:
    """Build a long-format macro frame from indicator -> daily values mapping."""
    start_d = pd.Timestamp(start)
    frames = []
    for indicator, values in indicators.items():
        dates = pd.bdate_range(start_d, periods=len(values))
        frames.append(
            pd.DataFrame({"date": [d.date() for d in dates], "indicator": indicator, "value": values, "source": "test"})
        )
    return pd.concat(frames, ignore_index=True)


def test_collect_bronze_empty_returns_canonical_schema(tmp_data_dir):
    df = collect_bronze()
    assert list(df.columns) == ["date", "indicator", "value", "source"]
    assert len(df) == 0


def test_collect_bronze_dedups_overlapping_dates(tmp_data_dir):
    """If two bronze fetches contain the same (date, indicator), keep one."""
    bronze_dir = tmp_data_dir / "bronze" / "macro" / "yfinance_macro"
    bronze_dir.mkdir(parents=True)
    d = date(2026, 4, 1)
    df1 = pd.DataFrame({"date": [d], "indicator": ["vix"], "value": [15.0], "source_symbol": ["^VIX"]})
    df2 = pd.DataFrame({"date": [d], "indicator": ["vix"], "value": [15.5], "source_symbol": ["^VIX"]})
    df1.to_parquet(bronze_dir / "2026-04-01.parquet", index=False)
    df2.to_parquet(bronze_dir / "2026-04-02.parquet", index=False)

    out = collect_bronze()
    assert len(out) == 1
    assert out["value"].iloc[0] in (15.0, 15.5)


def test_health_check_flags_out_of_bounds_and_zero():
    macro = _build_macro({"vix": [20.0, 25.0, 0.0, 500.0, 22.0]})
    clean, issues = check(macro)
    rules = {i.rule for i in issues}
    assert "zero" in rules
    assert "out_of_bounds" in rules
    # Both bad rows dropped
    assert len(clean) == 3


def test_health_check_passes_clean_data():
    macro = _build_macro({"vix": [20.0, 21.0, 19.0, 22.0]})
    clean, issues = check(macro)
    assert all(i.severity != "fail" for i in issues)
    assert len(clean) == 4


def test_percentile_endpoints_are_extreme():
    """The smallest value in a series should be at low percentile;
    the largest at high percentile (within the trailing window)."""
    n = 300
    values = list(np.linspace(10, 100, n))
    macro = _build_macro({"vix": values})
    pct = compute_percentiles(macro)

    last = pct[pct["indicator"] == "vix"].sort_values("date").iloc[-1]
    assert last["pct_1y"] >= 95.0  # last value is the max within 1Y window


def test_temperature_handles_missing_indicators_gracefully(tmp_path):
    """When a market has no indicators configured, calculator must skip it
    without affecting other markets. Uses an inline config (not the live yaml)
    so the test stays valid even as Phase 1b/2 add real CN/HK indicators."""
    # Inline config: only US has indicators; CN/HK explicitly empty.
    cfg = WeightsConfig(
        sub_weights={
            "cn": {"valuation": 0.5, "sentiment": 0.3, "liquidity": 0.2},
            "hk": {"valuation": 0.6, "sentiment": 0.25, "liquidity": 0.15},
            "us": {"valuation": 0.4, "sentiment": 0.35, "liquidity": 0.25},
        },
        indicator_weights={
            "us_valuation": {
                "us_pe_ttm": {"weight": 0.5, "direction": "+"},
                "us_cape": {"weight": 0.5, "direction": "+"},
            },
            "us_sentiment": {"vix": {"weight": 1.0, "direction": "-"}},
            "us_liquidity": {"dxy": {"weight": 1.0, "direction": "-"}},
            "cn_valuation": {},
            "cn_sentiment": {},
            "cn_liquidity": {},
            "hk_valuation": {},
            "hk_sentiment": {},
            "hk_liquidity": {},
        },
        percentile_window="pct_10y",
    )
    n = 50
    pct = pd.DataFrame(
        {
            "date": pd.bdate_range("2026-01-01", periods=n).date.tolist() * 4,
            "indicator": ["us_pe_ttm"] * n + ["us_cape"] * n + ["vix"] * n + ["dxy"] * n,
            "value": list(np.linspace(15, 30, n)) * 4,
            "pct_1y": [50.0] * (n * 4),
            "pct_5y": [60.0] * (n * 4),
            "pct_10y": [70.0] * (n * 4),
        }
    )
    temp = compute_temperature(pct, cfg)
    markets = set(temp["market"].unique())
    assert "us" in markets
    assert "cn" not in markets
    assert "hk" not in markets
    us_last = temp[temp["market"] == "us"].iloc[-1]
    assert us_last["data_quality"] == "ok"


def test_temperature_renormalizes_when_one_sub_unavailable(tmp_path):
    """If liquidity inputs are missing, valuation+sentiment must still produce
    a sensible overall (renormalized weights), with data_quality flagging."""
    cfg = WeightsConfig(
        sub_weights={"us": {"valuation": 0.4, "sentiment": 0.35, "liquidity": 0.25}},
        indicator_weights={
            "us_valuation": {
                "us_pe_ttm": {"weight": 0.5, "direction": "+"},
                "us_cape": {"weight": 0.5, "direction": "+"},
            },
            "us_sentiment": {"vix": {"weight": 1.0, "direction": "-"}},
            "us_liquidity": {"dxy": {"weight": 1.0, "direction": "-"}},
        },
        percentile_window="pct_10y",
    )
    n = 30
    pct = pd.DataFrame(
        {
            "date": pd.bdate_range("2026-01-01", periods=n).date.tolist() * 3,
            "indicator": ["us_pe_ttm"] * n + ["us_cape"] * n + ["vix"] * n,
            "value": [20.0] * (n * 3),
            "pct_1y": [50.0] * (n * 3),
            "pct_5y": [60.0] * (n * 3),
            "pct_10y": [80.0] * (n * 3),  # high valuation + low sentiment temp due to direction-
        }
    )
    temp = compute_temperature(pct, cfg)
    us = temp[temp["market"] == "us"].iloc[-1]
    assert us["data_quality"] == "liquidity_unavailable"
    assert not pd.isna(us["overall"])
    assert pd.isna(us["liquidity"])


def test_hk_publishable_during_cn_holiday_when_only_sentiment_missing():
    """HK rows whose only NaN sub-temp is sentiment AND fall on a CN-mainland-
    closed date must be marked is_publishable=True. Non-CN-closed dates with
    the same NaN pattern must NOT be publishable — the relaxation is calendar-
    gated, not "always tolerate missing sentiment"."""
    cfg = WeightsConfig(
        sub_weights={"hk": {"valuation": 0.6, "sentiment": 0.25, "liquidity": 0.15}},
        indicator_weights={
            "hk_valuation": {"hk_ewh_yield_ttm": {"weight": 1.0, "direction": "-"}},
            "hk_sentiment": {"cn_south_5d": {"weight": 1.0, "direction": "+"}},
            "hk_liquidity": {"hk_hibor_1m": {"weight": 1.0, "direction": "-"}},
        },
        percentile_window="pct_10y",
    )
    # Span a non-holiday Tuesday (2026-04-28) and a Labour-Day-week date
    # (2026-05-04, Monday — CN closed, HK open). Drop south-flow on 05-04
    # to mimic the real holiday data shape.
    dates = [date(2026, 4, 28), date(2026, 5, 4)]
    rows = []
    for d in dates:
        for ind in ["hk_ewh_yield_ttm", "hk_hibor_1m"]:
            rows.append({"date": d, "indicator": ind, "value": 50.0, "pct_1y": 50.0, "pct_5y": 50.0, "pct_10y": 50.0})
        # cn_south_5d only present on 04-28
        if d == date(2026, 4, 28):
            rows.append(
                {"date": d, "indicator": "cn_south_5d", "value": 100.0, "pct_1y": 60.0, "pct_5y": 60.0, "pct_10y": 60.0}
            )
    pct = pd.DataFrame(rows)

    temp = compute_temperature(pct, cfg)
    hk = temp[temp["market"] == "hk"].set_index("date")

    apr28 = hk.loc[pd.Timestamp("2026-04-28")]
    may04 = hk.loc[pd.Timestamp("2026-05-04")]

    # Sanity: 04-28 is fully complete; 05-04 is sentiment-NaN.
    assert bool(apr28["is_complete"]) is True
    assert pd.isna(may04["sentiment"])
    assert bool(may04["is_complete"]) is False

    # The relaxation kicks in on the CN-closed day only.
    assert int(may04["effective_completeness"]) == 3
    assert bool(may04["is_publishable"]) is True
    assert bool(apr28["is_publishable"]) is True


def test_hk_not_publishable_when_sentiment_missing_outside_cn_holiday():
    """If sentiment goes NaN on a regular CN trading day, that's a real data
    gap, not structural — must not be marked publishable."""
    cfg = WeightsConfig(
        sub_weights={"hk": {"valuation": 0.6, "sentiment": 0.25, "liquidity": 0.15}},
        indicator_weights={
            "hk_valuation": {"hk_ewh_yield_ttm": {"weight": 1.0, "direction": "-"}},
            "hk_sentiment": {"cn_south_5d": {"weight": 1.0, "direction": "+"}},
            "hk_liquidity": {"hk_hibor_1m": {"weight": 1.0, "direction": "-"}},
        },
        percentile_window="pct_10y",
    )
    # 2026-04-28 (Tue) is a normal CN trading day. Drop south flow.
    d = date(2026, 4, 28)
    rows = [
        {"date": d, "indicator": "hk_ewh_yield_ttm", "value": 50.0, "pct_1y": 50.0, "pct_5y": 50.0, "pct_10y": 50.0},
        {"date": d, "indicator": "hk_hibor_1m", "value": 50.0, "pct_1y": 50.0, "pct_5y": 50.0, "pct_10y": 50.0},
    ]
    pct = pd.DataFrame(rows)
    temp = compute_temperature(pct, cfg)
    hk = temp[temp["market"] == "hk"].iloc[-1]
    assert pd.isna(hk["sentiment"])
    assert bool(hk["is_publishable"]) is False
    assert int(hk["effective_completeness"]) == 2


def test_subtemp_ffill_carries_forward_within_limit():
    """A 1-day sentiment gap should be bridged by ffill: overall uses the
    prior day's sentiment, raw sub column stays NaN, *_ffilled flag flips on,
    is_publishable becomes True via the ffill excuse (not via structural-stale).
    Use 2026-04-29 (Wed, CN open) so cn-mainland-closed doesn't apply."""
    cfg = WeightsConfig(
        sub_weights={"hk": {"valuation": 0.6, "sentiment": 0.25, "liquidity": 0.15}},
        indicator_weights={
            "hk_valuation": {"hk_ewh_yield_ttm": {"weight": 1.0, "direction": "-"}},
            "hk_sentiment": {"cn_south_5d": {"weight": 1.0, "direction": "+"}},
            "hk_liquidity": {"hk_hibor_1m": {"weight": 1.0, "direction": "-"}},
        },
        percentile_window="pct_10y",
    )
    dates = [date(2026, 4, 27), date(2026, 4, 28), date(2026, 4, 29)]
    rows = []
    for d in dates:
        for ind in ["hk_ewh_yield_ttm", "hk_hibor_1m"]:
            rows.append({"date": d, "indicator": ind, "value": 50.0, "pct_1y": 50.0, "pct_5y": 50.0, "pct_10y": 50.0})
    # cn_south_5d only present on 04-27 and 04-28; missing on 04-29
    for d in [date(2026, 4, 27), date(2026, 4, 28)]:
        rows.append(
            {"date": d, "indicator": "cn_south_5d", "value": 100.0, "pct_1y": 80.0, "pct_5y": 80.0, "pct_10y": 80.0}
        )
    pct = pd.DataFrame(rows)

    temp = compute_temperature(pct, cfg)
    hk = temp[temp["market"] == "hk"].set_index("date")
    apr29 = hk.loc[pd.Timestamp("2026-04-29")]

    # Raw sentiment column stays NaN — we don't lie about which days had data.
    assert pd.isna(apr29["sentiment"])
    # But the ffill flag flips on, and overall was computed using carried value.
    assert bool(apr29["sentiment_ffilled"]) is True
    assert int(apr29["subtemp_ffilled"]) == 1
    assert bool(apr29["is_publishable"]) is True
    assert int(apr29["effective_completeness"]) == 3
    # Overall must reflect that sentiment=80 (carried) entered the weighted avg.
    # Sub temps: val = 100-50 = 50, sent = 80 (ffilled), liq = 100-50 = 50.
    # overall = 50*0.6 + 80*0.25 + 50*0.15 = 30 + 20 + 7.5 = 57.5
    assert abs(float(apr29["overall"]) - 57.5) < 1e-6


def test_subtemp_ffill_stops_after_limit():
    """When a sub is missing for more than SUBTEMP_FFILL_LIMIT_BDAYS trading
    days, the ffill grace expires: the row falls back to within-row
    re-normalization and is_publishable flips to False (outside structural-
    stale rule)."""
    cfg = WeightsConfig(
        sub_weights={"hk": {"valuation": 0.6, "sentiment": 0.25, "liquidity": 0.15}},
        indicator_weights={
            "hk_valuation": {"hk_ewh_yield_ttm": {"weight": 1.0, "direction": "-"}},
            "hk_sentiment": {"cn_south_5d": {"weight": 1.0, "direction": "+"}},
            "hk_liquidity": {"hk_hibor_1m": {"weight": 1.0, "direction": "-"}},
        },
        percentile_window="pct_10y",
    )
    # 5 consecutive non-holiday business days starting from a Monday.
    dates = list(pd.bdate_range("2026-04-13", periods=5).date)
    rows = []
    for d in dates:
        for ind in ["hk_ewh_yield_ttm", "hk_hibor_1m"]:
            rows.append({"date": d, "indicator": ind, "value": 50.0, "pct_1y": 50.0, "pct_5y": 50.0, "pct_10y": 50.0})
    # cn_south_5d only on day 0 — missing on days 1..4 (4 trading days), > limit of 3.
    rows.append(
        {"date": dates[0], "indicator": "cn_south_5d", "value": 100.0, "pct_1y": 80.0, "pct_5y": 80.0, "pct_10y": 80.0}
    )
    pct = pd.DataFrame(rows)
    temp = compute_temperature(pct, cfg)
    hk = temp[temp["market"] == "hk"].set_index("date")

    # Days 1-3 (within ffill window): publishable via ffill excuse.
    for i in (1, 2, 3):
        row = hk.loc[pd.Timestamp(dates[i])]
        assert bool(row["sentiment_ffilled"]) is True, f"day {i} should be ffilled"
        assert bool(row["is_publishable"]) is True, f"day {i} should be publishable"

    # Day 4 (beyond limit): ffill stops, sentiment stays NaN, not publishable.
    day4 = hk.loc[pd.Timestamp(dates[4])]
    assert pd.isna(day4["sentiment"])
    assert bool(day4["sentiment_ffilled"]) is False
    assert bool(day4["is_publishable"]) is False
    assert int(day4["effective_completeness"]) == 2


def test_sub_coverage_guard_triggers_ffill_when_minority_indicator_alone():
    """Reproduces the 2025-12-25 US-sentiment artifact: when only a minority-
    weight indicator (<50% of sub weight) is live, the sub must NOT report a
    re-normalized minority-only value — the coverage guard kicks it to NaN so
    sub-temp ffill carries the prior day's broader-based value forward."""
    cfg = WeightsConfig(
        sub_weights={"us": {"valuation": 0.4, "sentiment": 0.5, "liquidity": 0.1}},
        indicator_weights={
            "us_valuation": {"us_pe_ttm": {"weight": 1.0, "direction": "+"}},
            # 0.40 + 0.35 + 0.25 = 1.0; umich alone = 0.25 = below 0.5 guard.
            "us_sentiment": {
                "vix": {"weight": 0.40, "direction": "-"},
                "us_hy_oas": {"weight": 0.35, "direction": "-"},
                "us_umich_sentiment": {"weight": 0.25, "direction": "+"},
            },
            "us_liquidity": {"us_nfci": {"weight": 1.0, "direction": "-"}},
        },
        percentile_window="pct_10y",
    )
    dates = list(pd.bdate_range("2026-04-13", periods=3).date)
    rows = []
    # Day 0: all three sentiment indicators live (vix cold, hy_oas cold, umich
    # extreme cold) → sentiment ~ mid-30s.
    for ind, vals in [
        ("us_pe_ttm", 50.0),
        ("us_nfci", 50.0),
        ("vix", 30.0),
        ("us_hy_oas", 30.0),
        ("us_umich_sentiment", 5.0),
    ]:
        rows.append(
            {"date": dates[0], "indicator": ind, "value": vals, "pct_1y": vals, "pct_5y": vals, "pct_10y": vals}
        )
    # Day 1: only umich live in sentiment (mimics market-closed day). VIX +
    # HY drop out → coverage = 0.25, must trigger guard.
    for ind, vals in [
        ("us_pe_ttm", 50.0),
        ("us_nfci", 50.0),
        ("us_umich_sentiment", 5.0),
    ]:
        rows.append(
            {"date": dates[1], "indicator": ind, "value": vals, "pct_1y": vals, "pct_5y": vals, "pct_10y": vals}
        )
    # Day 2: full recovery.
    for ind, vals in [
        ("us_pe_ttm", 50.0),
        ("us_nfci", 50.0),
        ("vix", 30.0),
        ("us_hy_oas", 30.0),
        ("us_umich_sentiment", 5.0),
    ]:
        rows.append(
            {"date": dates[2], "indicator": ind, "value": vals, "pct_1y": vals, "pct_5y": vals, "pct_10y": vals}
        )

    pct = pd.DataFrame(rows)
    temp = compute_temperature(pct, cfg)
    us = temp[temp["market"] == "us"].set_index("date")

    day0 = us.loc[pd.Timestamp(dates[0])]
    day1 = us.loc[pd.Timestamp(dates[1])]
    day2 = us.loc[pd.Timestamp(dates[2])]

    # Day 0 sentiment computed from all three: vix(70) + hy_oas(70) + umich(5)
    # weighted 0.4/0.35/0.25 = 28 + 24.5 + 1.25 = 53.75
    assert abs(float(day0["sentiment"]) - 53.75) < 1e-6
    # Day 1: raw sentiment NaN (coverage guard), but ffilled value = day 0's.
    # We keep the raw column NaN so data-quality stays honest.
    assert pd.isna(day1["sentiment"])
    assert bool(day1["sentiment_ffilled"]) is True
    # Day 2: back to full coverage.
    assert abs(float(day2["sentiment"]) - 53.75) < 1e-6
    assert bool(day2["sentiment_ffilled"]) is False


def test_sub_coverage_guard_does_not_fire_for_hk_single_indicator():
    """HK sentiment runs with cn_south_5d alone (weight 1.0 after hk_vhsi was
    excluded from the live config). Coverage = 1.0 every day → guard must
    NOT fire. This pins the rule that the guard is about minority-weight
    fallback, not about absolute indicator count."""
    cfg = WeightsConfig(
        sub_weights={"hk": {"valuation": 0.6, "sentiment": 0.25, "liquidity": 0.15}},
        indicator_weights={
            "hk_valuation": {"hk_ewh_yield_ttm": {"weight": 1.0, "direction": "-"}},
            "hk_sentiment": {"cn_south_5d": {"weight": 1.0, "direction": "+"}},
            "hk_liquidity": {"hk_hibor_1m": {"weight": 1.0, "direction": "-"}},
        },
        percentile_window="pct_10y",
    )
    dates = list(pd.bdate_range("2026-04-13", periods=2).date)
    rows = []
    for d in dates:
        for ind, val in [("hk_ewh_yield_ttm", 50.0), ("cn_south_5d", 80.0), ("hk_hibor_1m", 50.0)]:
            rows.append({"date": d, "indicator": ind, "value": val, "pct_1y": val, "pct_5y": val, "pct_10y": val})
    pct = pd.DataFrame(rows)
    temp = compute_temperature(pct, cfg)
    hk = temp[temp["market"] == "hk"].set_index("date")
    for d in dates:
        row = hk.loc[pd.Timestamp(d)]
        # Sentiment must be the real cn_south_5d value, not NaN.
        assert not pd.isna(row["sentiment"]), f"{d}: sentiment unexpectedly NaN"
        assert abs(float(row["sentiment"]) - 80.0) < 1e-6
        assert bool(row["sentiment_ffilled"]) is False


def test_derive_indicators_computes_us_erp_with_monthly_pe_ffill():
    """ERP = 100/PE − real_yield. PE published only first-of-month (mimicking
    multpl's actual monthly cadence); real_yield daily. Verifies the ffill
    path actually works — not the previous test's all-aligned-daily fixture
    which would pass even if ffill was broken."""
    # Real yield: daily, 60 business days
    daily_dates = pd.bdate_range("2026-01-01", periods=60)
    # PE: only the 3 month-start rows (Jan/Feb/Mar 2026) — must ffill to fill the gaps
    pe_dates = [pd.Timestamp("2026-01-02"), pd.Timestamp("2026-02-02"), pd.Timestamp("2026-03-02")]
    macro = pd.concat(
        [
            pd.DataFrame(
                {
                    "date": [d.date() for d in pe_dates],
                    "indicator": "us_pe_ttm",
                    "value": [20.0, 22.0, 25.0],  # changes month-over-month so ffill mistakes are detectable
                    "source": "multpl",
                }
            ),
            pd.DataFrame(
                {
                    "date": [d.date() for d in daily_dates],
                    "indicator": "us10y_real_yield",
                    "value": [1.5] * len(daily_dates),
                    "source": "fred",
                }
            ),
        ],
        ignore_index=True,
    )
    out = derive_indicators(macro)
    erp = out[out["indicator"] == "us_erp"].copy()
    erp["date"] = pd.to_datetime(erp["date"])
    erp = erp.set_index("date").sort_index()

    assert not erp.empty
    # Mid-January (PE=20, EY=5%) → ERP = 5 − 1.5 = 3.5
    jan_15 = erp.loc["2026-01-15"]
    assert 3.4 < jan_15["value"] < 3.6, f"Jan ffill broken: got {jan_15['value']}"
    # Mid-February (PE=22, EY=4.545%) → ERP = 4.545 − 1.5 = 3.045
    feb_15 = erp.loc["2026-02-13"]  # last bday before Feb 15 weekend
    assert 3.0 < feb_15["value"] < 3.1, f"Feb ffill picked wrong PE: got {feb_15['value']}"
    # Mid-March (PE=25, EY=4.0%) → ERP = 4.0 − 1.5 = 2.5
    mar_15 = erp.loc["2026-03-13"]
    assert 2.45 < mar_15["value"] < 2.55, f"Mar ffill picked wrong PE: got {mar_15['value']}"
    assert (out[out["indicator"] == "us_erp"]["source"] == "derived").all()


def test_derive_indicators_guards_against_non_positive_pe():
    """If multpl returns PE=0 (parse error) or PE<0 (historical 2009Q1
    negative-EPS scenario), ERP must NOT produce inf or sign-flipped values
    that would later get inverted by direction:'-' in weights.yaml into
    bogus 'extreme hot' US valuation readings."""
    dates = pd.bdate_range("2026-01-01", periods=10)
    macro = pd.DataFrame(
        {
            "date": [d.date() for d in dates] * 2,
            "indicator": ["us_pe_ttm"] * 10 + ["us10y_real_yield"] * 10,
            # Mix of poison values: 0, negative, and one valid 20.0 at the end
            "value": [0.0, 0.0, -5.0, -2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 20.0] + [1.5] * 10,
            "source": ["multpl"] * 10 + ["fred"] * 10,
        }
    )
    out = derive_indicators(macro)
    erp = out[out["indicator"] == "us_erp"]
    # Only the last row (PE=20) should produce a valid ERP. All others guarded.
    assert len(erp) == 1, f"expected 1 valid ERP, got {len(erp)}: {erp['value'].tolist()}"
    assert 3.4 < erp["value"].iloc[0] < 3.6
    # Critically: no inf or negative ERP smuggled through
    import numpy as np

    assert not np.isinf(erp["value"]).any()


def test_weights_config_rejects_unbalanced_block(tmp_path):
    """Sub-block weights MUST sum to 1.0; loading an unbalanced config
    must raise immediately, not silently produce miscalibrated temperatures."""
    bad_yaml = tmp_path / "bad_weights.yaml"
    bad_yaml.write_text(
        """sub_weights:
  us: { valuation: 1.0, sentiment: 0.0, liquidity: 0.0 }
indicator_weights:
  us_valuation:
    us_pe_ttm: { weight: 0.5, direction: "+" }
    us_cape:   { weight: 0.7, direction: "+" }
percentile_window: pct_10y
"""
    )
    with pytest.raises(ValueError, match="sums to"):
        WeightsConfig.load(bad_yaml)


def test_weights_config_rejects_inconsistent_window_override(tmp_path):
    """Same indicator across blocks must use the same window override —
    otherwise window_for() returns whichever block iterates first."""
    bad_yaml = tmp_path / "bad_window.yaml"
    bad_yaml.write_text(
        """sub_weights:
  us: { valuation: 0.5, sentiment: 0.5, liquidity: 0.0 }
  hk: { valuation: 0.0, sentiment: 0.0, liquidity: 1.0 }
indicator_weights:
  us_valuation:
    dxy: { weight: 1.0, direction: "-", window: pct_5y }
  us_sentiment: {}
  hk_liquidity:
    dxy: { weight: 1.0, direction: "-", window: pct_10y }
percentile_window: pct_10y
"""
    )
    with pytest.raises(ValueError, match="inconsistent"):
        WeightsConfig.load(bad_yaml)


def test_derive_indicators_skips_when_inputs_missing():
    """If only us_pe_ttm exists (no real yield), us_erp should NOT be emitted
    rather than producing NaN/garbage rows."""
    n = 10
    dates = pd.bdate_range("2026-01-01", periods=n)
    macro = pd.DataFrame(
        {
            "date": [d.date() for d in dates],
            "indicator": "us_pe_ttm",
            "value": [22.0] * n,
            "source": "multpl",
        }
    )
    out = derive_indicators(macro)
    assert "us_erp" not in out["indicator"].unique()


def test_temperature_per_indicator_window_override():
    """An indicator with window: pct_5y must read pct_5y; without override
    must read the global percentile_window. Verifies refactor of pct_wide
    construction picks up per-indicator columns."""
    cfg = WeightsConfig(
        sub_weights={"us": {"valuation": 1.0, "sentiment": 0.0, "liquidity": 0.0}},
        indicator_weights={
            "us_valuation": {
                # us_pe_ttm uses default (pct_10y); us_cape overrides to pct_5y.
                "us_pe_ttm": {"weight": 0.5, "direction": "+"},
                "us_cape": {"weight": 0.5, "direction": "+", "window": "pct_5y"},
            },
            "us_sentiment": {},
            "us_liquidity": {},
        },
        percentile_window="pct_10y",
    )
    n = 30
    pct = pd.DataFrame(
        {
            "date": pd.bdate_range("2026-01-01", periods=n).date.tolist() * 2,
            "indicator": ["us_pe_ttm"] * n + ["us_cape"] * n,
            "value": [20.0] * (n * 2),
            "pct_1y": [10.0] * (n * 2),
            # pe_ttm reads pct_10y=80; cape reads pct_5y=40 (override).
            # Equal weight → val ~= (80 + 40) / 2 = 60.
            "pct_5y": [99.0] * n + [40.0] * n,  # pe_ttm 99 must NOT be picked
            "pct_10y": [80.0] * n + [99.0] * n,  # cape 99 must NOT be picked
        }
    )
    temp = compute_temperature(pct, cfg)
    last = temp[temp["market"] == "us"].iloc[-1]
    assert 55.0 < last["valuation"] < 65.0, f"expected ~60, got {last['valuation']}"


def test_divergence_detects_signal_pair_disagreement():
    macro = _build_macro(
        {
            # SP500 up 1% each day, VIX up 1% each day → divergence (expected: opposite)
            "sp500": [100.0, 101.0, 102.0, 103.0],
            "vix": [20.0, 20.2, 20.4, 20.6],
        }
    )
    div = compute_divergence(macro)
    sp500_vix = div[div["pair_name"] == "sp500_vix"]
    # All non-first days are divergent (both rising)
    assert sp500_vix["is_divergent"].all()


def test_divergence_strength_is_product_scaled_by_100():
    macro = _build_macro(
        {
            # Day 2: SP500 +2%, VIX +10% → strength = 0.02 * 0.10 * 100 = 0.2.
            "sp500": [100.0, 102.0],
            "vix": [20.0, 22.0],
        }
    )
    div = compute_divergence(macro)
    sp500_vix = div[div["pair_name"] == "sp500_vix"].iloc[0]
    assert bool(sp500_vix["is_divergent"]) is True
    assert sp500_vix["strength"] == pytest.approx(0.2)


def test_divergence_skips_pairs_missing_indicators():
    macro = _build_macro({"sp500": [100.0, 101.0, 102.0]})  # no vix
    div = compute_divergence(macro)
    assert "sp500_vix" not in div["pair_name"].unique()
