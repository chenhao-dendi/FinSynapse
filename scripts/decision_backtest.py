#!/usr/bin/env python3
r"""Decision backtest: translate temperature into a hypothetical allocation
and measure its performance. **Not a trading strategy** — this is a proxy
for the temperature metric's cross-sectional discriminative power.

Rule
----
    temperature >= 80  ->   0% index (overheated — stay out)
    temperature <= 30  -> 100% index (freezing — go all-in)
    otherwise          -> linear interpolation: (80 - temp) / 50

Runs base case + sensitivity (+-10 pp threshold shift) and reports:
  CAGR, Sharpe, Sortino, max drawdown, annual vol, turnover, hit rate.

Usage:
    uv run python scripts/decision_backtest.py
    uv run python scripts/decision_backtest.py --temp <path> --macro <path>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import empyrical as ep
except ImportError:
    ep = None  # type: ignore[assignment]

INDEX_MAP = {"us": "sp500", "cn": "csi300", "hk": "hsi"}
MARKETS = ("cn", "hk", "us")
ANNUALIZATION = "daily"

DISCLAIMER = (
    "这不是交易策略，是温度区分度的可观察代理指标。\n"
    "This is NOT a trading strategy — it is an observable proxy for the temperature "
    "metric's discriminative power."
)


def _allocation_curve(temp: pd.Series, cold: float = 30, hot: float = 80) -> pd.Series:
    alloc = (hot - temp) / (hot - cold)
    return alloc.clip(0, 1)


def _run_single(
    prices: pd.Series,
    temp_series: pd.Series,
    cold: float,
    hot: float,
) -> dict:
    alloc = _allocation_curve(temp_series, cold, hot)

    idx_ret = prices.pct_change().dropna()
    common = alloc.index.intersection(idx_ret.index)
    if len(common) < 60:
        return {"error": "insufficient data", "n_days": len(common)}

    a = alloc.loc[common]
    r = idx_ret.loc[common]
    strat_ret = a.shift(1) * r
    strat_ret = strat_ret.dropna()

    turnover = a.diff().abs()

    if ep is not None:
        cagr = ep.cagr(strat_ret, period=ANNUALIZATION)
        sharpe = ep.sharpe_ratio(strat_ret, period=ANNUALIZATION)
        sortino = ep.sortino_ratio(strat_ret, period=ANNUALIZATION)
        max_dd = ep.max_drawdown(strat_ret)
        ann_vol = ep.annual_volatility(strat_ret, period=ANNUALIZATION)
    else:
        cum = (1 + strat_ret).prod()
        cagr = float(cum ** (ANNUALIZATION / len(strat_ret)) - 1)
        ann_vol = float(strat_ret.std() * np.sqrt(ANNUALIZATION))
        sharpe = float(cagr / ann_vol) if ann_vol > 0 else 0.0
        sortino = None
        max_dd = None

    next_day_sign = np.sign(r.shift(-1).loc[common])
    alloc_dir = (a - 0.5).loc[common]
    correct = (alloc_dir * next_day_sign > 0).sum()
    total = (~next_day_sign.isna() & (alloc_dir != 0)).sum()
    hit_rate = float(correct / total) if total > 0 else None

    def _r(v: float | None, d: int = 4) -> float | None:
        return round(float(v), d) if v is not None else None

    return {
        "cold_threshold": cold,
        "hot_threshold": hot,
        "n_days": len(common),
        "cagr": _r(cagr),
        "sharpe": _r(sharpe),
        "sortino": _r(sortino),
        "max_drawdown": _r(max_dd),
        "annual_volatility": _r(ann_vol),
        "turnover_pct": round(float(turnover.mean() * 100), 2),
        "hit_rate": _r(hit_rate),
    }


def _load_data(temp_path: Path, macro_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    temp = pd.read_parquet(temp_path)
    temp["date"] = pd.to_datetime(temp["date"])
    macro = pd.read_parquet(macro_path)
    wide = macro.pivot_table(index="date", columns="indicator", values="value").sort_index()
    wide.index = pd.to_datetime(wide.index)
    return temp, wide


def main() -> int:
    parser = argparse.ArgumentParser(description="Decision backtest — temperature allocation proxy")
    parser.add_argument("--temp", type=Path, help="Path to temperature_daily.parquet")
    parser.add_argument("--macro", type=Path, help="Path to macro_daily.parquet")
    args = parser.parse_args()

    temp_path = args.temp or Path("tests/fixtures/eval_silver_2026Q1/temperature_daily.parquet")
    macro_path = args.macro or Path("tests/fixtures/eval_silver_2026Q1/macro_daily.parquet")

    temp, wide = _load_data(temp_path, macro_path)

    print("=" * 72)
    print("  Decision Backtest — Temperature Allocation (pseudo-strategy)")
    print("=" * 72)
    print()
    print(DISCLAIMER)
    print()

    t_min = temp["date"].min().strftime("%Y-%m-%d")
    t_max = temp["date"].max().strftime("%Y-%m-%d")
    print(f"data: {t_min} -> {t_max}")

    for market in MARKETS:
        idx_col = INDEX_MAP.get(market)
        if idx_col not in wide.columns:
            continue

        prices = wide[idx_col].dropna()
        sub = temp[temp["market"] == market].copy()
        sub = sub.set_index("date").sort_index()
        temp_series = sub["overall"].dropna()

        base = _run_single(prices, temp_series, 30, 80)
        wider = _run_single(prices, temp_series, 20, 90)
        tighter = _run_single(prices, temp_series, 40, 70)

        print(f"\n{market.upper()} ({idx_col})")
        hdr = f"  {'case':<16} {'CAGR':>9} {'Sharpe':>8} {'Sortino':>8} {'maxDD':>8} {'vol':>8} {'turn':>7} {'hit':>7}"
        print(hdr)
        print("  " + "-" * (len(hdr) - 2))

        for label, r in [("base   30/80", base), ("wider  20/90", wider), ("tighter 40/70", tighter)]:
            if "error" in r:
                print(f"  {label:<16} {r['error']}")
                continue
            cagr_s = f"{r['cagr']:.2%}" if r["cagr"] is not None else "N/A"
            sharpe_s = f"{r['sharpe']:.2f}" if r["sharpe"] is not None else "N/A"
            sortino_s = f"{r['sortino']:.2f}" if r["sortino"] is not None else "N/A"
            dd_s = f"{r['max_drawdown']:.2%}" if r["max_drawdown"] is not None else "N/A"
            vol_s = f"{r['annual_volatility']:.2%}" if r["annual_volatility"] is not None else "N/A"
            to_s = f"{r['turnover_pct']:.1f}%"
            hit_s = f"{r['hit_rate']:.3f}" if r["hit_rate"] is not None else "N/A"
            print(
                f"  {label:<16} {cagr_s:>9} {sharpe_s:>8} {sortino_s:>8} {dd_s:>8} {vol_s:>8} {to_s:>7} {hit_s:>7}"
            )

    print()
    print(DISCLAIMER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
