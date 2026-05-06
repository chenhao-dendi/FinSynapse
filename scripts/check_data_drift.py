#!/usr/bin/env python3
"""Data drift detection for FinSynapse indicators.

Compares indicator distributions between two time windows using
the two-sample Kolmogorov-Smirnov test. Detects regime shifts
that could silently invalidate the percentile baseline.

Usage:
    uv run python scripts/check_data_drift.py
    uv run python scripts/check_data_drift.py --window-a 2018-01-01:2019-12-31 --window-b 2022-01-01:2023-12-31
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "eval_silver_2026Q1"

INDICATORS_OF_INTEREST = [
    "sp500", "csi300", "hsi",
    "vix", "dxy", "us_pe_ttm", "us_cape",
    "csi300_pe_ttm", "csi300_pb",
    "us10y_real_yield", "us_nfci",
    "cn_m2_yoy", "hk_vhsi",
]

ALPHA = 0.01  # significance threshold


def _load_macro(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _ks_test(series_a: pd.Series, series_b: pd.Series) -> dict:
    a = series_a.dropna().values
    b = series_b.dropna().values
    if len(a) < 30 or len(b) < 30:
        return {"statistic": None, "p_value": None, "mean_a": None, "mean_b": None, "std_a": None, "std_b": None, "mean_shift_pct": None, "drift": "insufficient_data"}

    ks_stat, p_value = stats.ks_2samp(a, b)
    mean_a = float(np.mean(a))
    mean_b = float(np.mean(b))
    std_a = float(np.std(a))
    std_b = float(np.std(b))

    return {
        "statistic": round(float(ks_stat), 4),
        "p_value": round(float(p_value), 6),
        "mean_a": round(mean_a, 4),
        "mean_b": round(mean_b, 4),
        "std_a": round(std_a, 4),
        "std_b": round(std_b, 4),
        "mean_shift_pct": round((mean_b - mean_a) / abs(mean_a) * 100, 2) if mean_a != 0 else None,
        "drift": "significant" if p_value < ALPHA else "stable",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect data drift between two time windows")
    parser.add_argument(
        "--window-a",
        type=str,
        default="2015-01-01:2019-12-31",
        help="First time window (YYYY-MM-DD:YYYY-MM-DD)",
    )
    parser.add_argument(
        "--window-b",
        type=str,
        default="2020-01-01:2024-12-31",
        help="Second time window (YYYY-MM-DD:YYYY-MM-DD)",
    )
    parser.add_argument("--macro", type=Path, default=FIXTURE_DIR / "macro_daily.parquet")
    args = parser.parse_args()

    a_start, a_end = args.window_a.split(":")
    b_start, b_end = args.window_b.split(":")

    macro = _load_macro(args.macro)
    wide = macro.pivot_table(index="date", columns="indicator", values="value").sort_index()
    wide.index = pd.to_datetime(wide.index)

    print("=" * 72)
    print("  Data Drift Detection — KS Test")
    print(f"  Window A: {a_start} → {a_end}")
    print(f"  Window B: {b_start} → {b_end}")
    print("=" * 72)
    print()

    mask_a = (wide.index >= a_start) & (wide.index <= a_end)
    mask_b = (wide.index >= b_start) & (wide.index <= b_end)

    header = f"{'indicator':<24} {'KS stat':>9} {'p-value':>11} {'mean A':>10} {'mean B':>10} {'shift%':>8} {'verdict':>12}"
    print(header)
    print("-" * len(header))

    drifts: list[dict] = []
    for ind in INDICATORS_OF_INTEREST:
        if ind not in wide.columns:
            continue
        result = _ks_test(wide.loc[mask_a, ind], wide.loc[mask_b, ind])
        result["indicator"] = ind
        drifts.append(result)

        ks_s = f"{result.get('statistic', 'N/A'):.4f}" if result.get("statistic") is not None else "N/A"
        pv_s = f"{result.get('p_value', 'N/A'):.6f}" if result.get("p_value") is not None else "N/A"
        ma_s = f"{result.get('mean_a', 'N/A'):.2f}" if result.get("mean_a") is not None else "N/A"
        mb_s = f"{result.get('mean_b', 'N/A'):.2f}" if result.get("mean_b") is not None else "N/A"
        sh_s = f"{result.get('mean_shift_pct', 'N/A'):.1f}%" if result.get("mean_shift_pct") is not None else "N/A"
        flag = "!! DRIFT !!" if result["drift"] == "significant" else "ok"

        print(f"{ind:<24} {ks_s:>9} {pv_s:>11} {ma_s:>10} {mb_s:>10} {sh_s:>8} {flag:>12}")

    significant = [d for d in drifts if d["drift"] == "significant"]
    print()
    if significant:
        print(f"DRIFT DETECTED in {len(significant)}/{len(drifts)} indicators (α={ALPHA}):")
        for d in significant:
            print(f"  {d['indicator']}: KS={d['statistic']:.4f}, p={d['p_value']:.6f}, "
                  f"shift={d['mean_shift_pct']:.1f}%")
        return 1
    else:
        print(f"No significant drift detected ({len(drifts)} indicators, α={ALPHA}).")
        return 0


if __name__ == "__main__":
    sys.exit(main())
