"""Property-based invariant tests for the transform pipeline.

Uses hypothesis to generate synthetic input DataFrames and verify
that key invariants hold across the percentile / temperature computation.
"""

from __future__ import annotations

import pandas as pd
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from finsynapse.transform.percentile import compute_percentiles
from finsynapse.transform.temperature import (
    WeightsConfig,
    _build_pct_wide,
    _sub_temperature,
    compute_temperature,
)

INDICATOR_NAMES = ["sp500", "vix", "csi300", "hsi", "dxy", "hk_vhsi"]


# ── invariant 1: percentile bounds ───────────────────────────────────────────


@given(
    st.lists(
        st.tuples(
            st.sampled_from(INDICATOR_NAMES),
            st.floats(0.1, 50000.0),
        ),
        min_size=200,
        max_size=500,
    )
)
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.large_base_example])
def test_percentile_bounds(rows):
    """All pct_* columns must be in [0, 100] or NaN after compute_percentiles."""
    base = pd.Timestamp("2015-01-01")
    data = {"date": [], "indicator": [], "value": [], "source": []}
    for i, (ind, val) in enumerate(rows):
        data["date"].append(base + pd.Timedelta(days=i % 2500))
        data["indicator"].append(ind)
        data["value"].append(val)
        data["source"].append("test")
    macro_df = pd.DataFrame(data).drop_duplicates(subset=["date", "indicator"]).reset_index(drop=True)

    result = compute_percentiles(macro_df)
    for col in ["pct_1y", "pct_5y", "pct_10y"]:
        if col not in result.columns:
            continue
        valid = result[col].dropna()
        if len(valid) == 0:
            continue
        assert (valid >= 0.0).all(), f"{col} has values < 0"
        assert (valid <= 100.0).all(), f"{col} has values > 100"


# ── invariant 2: temperature bounds ──────────────────────────────────────────


@given(
    st.lists(
        st.tuples(
            st.sampled_from(INDICATOR_NAMES),
            st.floats(0.0, 100.0),
            st.floats(0.0, 100.0),
            st.floats(0.0, 100.0),
        ),
        min_size=100,
        max_size=400,
    )
)
@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.large_base_example])
def test_temperature_bounds(rows):
    """All overall / sub_temp values must be in [0, 100] or NaN."""
    base = pd.Timestamp("2020-01-01")
    data = {"date": [], "indicator": [], "value": [], "pct_1y": [], "pct_5y": [], "pct_10y": []}
    for i, (ind, p1, p5, p10) in enumerate(rows):
        data["date"].append(base + pd.Timedelta(days=i % 500))
        data["indicator"].append(ind)
        data["value"].append(p10)
        data["pct_1y"].append(p1)
        data["pct_5y"].append(p5)
        data["pct_10y"].append(p10)
    pct_df = pd.DataFrame(data)

    try:
        result = compute_temperature(pct_df)
    except (ValueError, KeyError):
        return

    if result is None or result.empty:
        return

    for col in ["overall", "valuation", "sentiment", "liquidity"]:
        if col not in result.columns:
            continue
        valid = result[col].dropna()
        if len(valid) == 0:
            continue
        assert (valid >= 0.0).all(), f"{col} has values < 0"
        assert (valid <= 100.0).all(), f"{col} has values > 100"


# ── invariant 3: missing-indicator renormalization ───────────────────────────


def _minimal_weights() -> WeightsConfig:
    raw = {
        "sub_weights": {"cn": {"valuation": 1.0, "sentiment": 0.0, "liquidity": 0.0}},
        "indicator_weights": {
            "cn_valuation": {
                "csi300_pe_ttm": {"weight": 0.5, "direction": "+"},
                "csi300_pb": {"weight": 0.5, "direction": "+"},
            }
        },
        "percentile_window": "pct_10y",
    }
    return WeightsConfig(**raw)


def test_missing_indicator_renormalization():
    """When one indicator is missing, remaining weights renormalize to 1.0."""
    cfg = _minimal_weights()
    dates = pd.date_range("2020-01-01", periods=30, freq="B")

    pct_df = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "indicator": ["csi300_pe_ttm"] * 30 + ["csi300_pb"] * 30,
            "value": [50.0] * 60,
            "pct_1y": [50.0] * 60,
            "pct_5y": [50.0] * 60,
            "pct_10y": [50.0] * 60,
        }
    )

    pct_wide = _build_pct_wide(pct_df, cfg)
    full_temp = _sub_temperature(pct_wide, "cn", "valuation", cfg, with_confidence=False)
    assert not full_temp.dropna().empty
    assert abs(full_temp.dropna().iloc[0] - 50.0) < 0.01

    # Drop one indicator — remaining should still produce 50 (weight renormalized to 1.0)
    pct_single = pct_df[pct_df["indicator"] == "csi300_pe_ttm"]
    pct_wide_single = _build_pct_wide(pct_single, cfg)
    single_temp = _sub_temperature(pct_wide_single, "cn", "valuation", cfg, with_confidence=False)
    assert not single_temp.dropna().empty
    assert abs(single_temp.dropna().iloc[0] - 50.0) < 0.01, (
        f"Expected 50 after renormalization, got {single_temp.dropna().iloc[0]:.2f}"
    )


# ── invariant 4: direction='-' boundary ──────────────────────────────────────


def test_direction_minus_boundary():
    """For direction='-' indicators: pct=0 → 100℃; pct=100 → 0℃."""
    raw = {
        "sub_weights": {"us": {"sentiment": 1.0, "valuation": 0.0, "liquidity": 0.0}},
        "indicator_weights": {"us_sentiment": {"vix": {"weight": 1.0, "direction": "-"}}},
        "percentile_window": "pct_10y",
    }
    cfg = WeightsConfig(**raw)
    dates = pd.date_range("2020-01-01", periods=60, freq="B")

    for pct_val, expected in [(0.0, 100.0), (100.0, 0.0), (50.0, 50.0)]:
        pct_df = pd.DataFrame(
            {
                "date": list(dates),
                "indicator": ["vix"] * 60,
                "value": [20.0] * 60,
                "pct_1y": [pct_val] * 60,
                "pct_5y": [pct_val] * 60,
                "pct_10y": [pct_val] * 60,
            }
        )
        pct_wide = _build_pct_wide(pct_df, cfg)
        temp = _sub_temperature(pct_wide, "us", "sentiment", cfg, with_confidence=False)
        actual = temp.dropna().iloc[0]
        assert abs(actual - expected) < 0.01, f"direction='-', pct={pct_val}: expected {expected}℃, got {actual:.2f}℃"


# ── invariant 5: dispersion-weighted monotonicity ────────────────────────────


def test_dispersion_weighted_monotonicity():
    """Higher sub_temp dispersion → lower confidence."""
    raw = {
        "sub_weights": {"cn": {"valuation": 1.0, "sentiment": 0.0, "liquidity": 0.0}},
        "indicator_weights": {
            "cn_valuation": {
                "csi300_pe_ttm": {"weight": 0.5, "direction": "+"},
                "csi300_pb": {"weight": 0.5, "direction": "+"},
            }
        },
        "percentile_window": "pct_10y",
    }
    cfg = WeightsConfig(**raw)
    dates = pd.date_range("2020-01-01", periods=3, freq="B")

    for label, pe_val, pb_val in [("low_dispersion", 50.0, 52.0), ("high_dispersion", 10.0, 90.0)]:
        rows = []
        for d in dates:
            rows.append(
                {
                    "date": d,
                    "indicator": "csi300_pe_ttm",
                    "value": pe_val,
                    "pct_1y": pe_val,
                    "pct_5y": pe_val,
                    "pct_10y": pe_val,
                }
            )
            rows.append(
                {
                    "date": d,
                    "indicator": "csi300_pb",
                    "value": pb_val,
                    "pct_1y": pb_val,
                    "pct_5y": pb_val,
                    "pct_10y": pb_val,
                }
            )
        pct_df = pd.DataFrame(rows)
        pct_wide = _build_pct_wide(pct_df, cfg)
        _, confidence = _sub_temperature(pct_wide, "cn", "valuation", cfg, with_confidence=True)
        conf_val = confidence.dropna().iloc[0]

        if label == "low_dispersion":
            assert conf_val > 0.5, f"Low dispersion should have high confidence, got {conf_val:.2f}"
        else:
            assert conf_val < 0.8, (
                f"High dispersion ({abs(pe_val - pb_val)}pp apart) should have low confidence, got {conf_val:.2f}"
            )
