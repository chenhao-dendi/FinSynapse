"""Evaluation metrics: pivot hit rates, forward-return Spearman rho, rolling OOS IC.

All functions are pure: they take DataFrames/lists as input, return computed
values. No file I/O, no global state, no side effects.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from finsynapse.transform.temperature import MARKETS

FORWARD_HORIZONS = {"1m": 21, "3m": 63, "6m": 126, "12m": 252}
INDEX_MAP = {"us": "sp500", "cn": "csi300", "hk": "hsi"}
SCIPY_AVAILABLE = False
try:
    from scipy import stats as _scipy_stats

    SCIPY_AVAILABLE = True
except ImportError:
    pass


@dataclass
class PivotEvalRow:
    label: str
    market: str
    pivot_date: date
    expected_zone: str
    temperature: float
    zone: str
    directional_pass: bool
    strict_pass: bool


def _load_pivots(pivots_path: Path) -> list[dict]:
    import yaml

    with pivots_path.open() as f:
        raw = yaml.safe_load(f)
    return raw["pivots"]


def compute_pivot_rates(
    temp_df: pd.DataFrame,
    pivots_path: Path,
) -> tuple[float, float, dict[str, dict], list[PivotEvalRow]]:
    """Compute pivot directional/strict hit rates.

    Returns:
        directional_rate: overall hit rate (0.0-1.0)
        strict_rate: overall strict hit rate (0.0-1.0)
        per_market: per-market rates
        eval_rows: per-pivot evaluation detail
    """
    pivots = _load_pivots(pivots_path)
    tdf = temp_df.copy()
    tdf["date"] = pd.to_datetime(tdf["date"])

    eval_rows: list[PivotEvalRow] = []
    for p in pivots:
        target = pd.Timestamp(p["date"])
        market = p["market"]
        expected = p["expected_zone"]

        sub = tdf[(tdf["market"] == market) & (tdf["date"] <= target)].sort_values("date").tail(1)
        if sub.empty:
            continue

        overall = float(sub.iloc[0]["overall"])
        if pd.isna(overall):
            continue

        z = "hot" if overall >= 70 else ("cold" if overall < 30 else "mid")

        directional = False
        if expected == "cold":
            directional = overall < 50
        elif expected == "hot":
            directional = overall > 50
        else:
            directional = 25 <= overall <= 75

        strict = False
        if expected == "hot":
            strict = overall >= 70
        elif expected == "cold":
            strict = 0 <= overall < 30
        elif expected == "mid":
            strict = 30 <= overall < 70

        eval_rows.append(
            PivotEvalRow(
                label=p["label"],
                market=market,
                pivot_date=target.date(),
                expected_zone=expected,
                temperature=overall,
                zone=z,
                directional_pass=directional,
                strict_pass=strict,
            )
        )

    total = len(eval_rows)
    directional_hits = sum(1 for r in eval_rows if r.directional_pass)
    strict_hits = sum(1 for r in eval_rows if r.strict_pass)

    per_market: dict[str, dict] = {}
    for mkt in MARKETS:
        market_rows = [r for r in eval_rows if r.market == mkt]
        n = len(market_rows)
        per_market[mkt] = {
            "n_pivots": n,
            "directional_rate": round(sum(1 for r in market_rows if r.directional_pass) / n, 4) if n else 0,
            "strict_rate": round(sum(1 for r in market_rows if r.strict_pass) / n, 4) if n else 0,
        }

    return (
        round(directional_hits / total, 4) if total else 0,
        round(strict_hits / total, 4) if total else 0,
        per_market,
        eval_rows,
    )


def compute_forward_rho(
    macro_long: pd.DataFrame,
    temp_df: pd.DataFrame,
) -> dict[str, dict[str, float | None]]:
    """Compute Spearman rho between temperature and forward returns.

    Returns nested dict: {market: {horizon: rho}}
    """
    if not SCIPY_AVAILABLE:
        return {m: {h: None for h in FORWARD_HORIZONS} for m in MARKETS}

    wide = macro_long.pivot_table(index="date", columns="indicator", values="value").sort_index()
    wide.index = pd.to_datetime(wide.index)

    tdf = temp_df.copy()
    tdf["date"] = pd.to_datetime(tdf["date"])

    result: dict[str, dict[str, float | None]] = {}

    for market, idx_ticker in INDEX_MAP.items():
        if idx_ticker not in wide.columns:
            result[market] = {h: None for h in FORWARD_HORIZONS}
            continue

        prices = wide[idx_ticker].dropna()
        sub = tdf[tdf["market"] == market].copy()

        horizon_pairs: dict[str, tuple[list[float], list[float]]] = {h: ([], []) for h in FORWARD_HORIZONS}

        for _, row in sub.iterrows():
            t = pd.Timestamp(row["date"])
            if t not in prices.index:
                continue

            t_pos = prices.index.get_loc(t)
            n_prices = len(prices.index)
            current = prices.iloc[t_pos]

            for label, days in FORWARD_HORIZONS.items():
                fwd_pos = t_pos + days
                if fwd_pos >= n_prices:
                    continue
                fwd_return = float(prices.iloc[fwd_pos] / current - 1.0)
                horizon_pairs[label][0].append(float(row["overall"]))
                horizon_pairs[label][1].append(fwd_return)

        market_result: dict[str, float | None] = {}
        for horizon in FORWARD_HORIZONS:
            xs, ys = horizon_pairs[horizon]
            if len(xs) < 30:
                market_result[horizon] = None
                continue
            from scipy import stats

            rho, _ = stats.spearmanr(xs, ys)
            market_result[horizon] = float(rho) if not np.isnan(rho) else None

        result[market] = market_result

    return result


def _rolling_ic_single(
    rows: list[tuple[date, float, float | None]],
    window_months: int = 36,
    step_months: int = 3,
    min_obs: int = 30,
) -> dict:
    """Compute rolling IC for a single series of (date, temperature, forward_return)."""
    valid = [(d, t, r) for d, t, r in rows if r is not None]
    if len(valid) < min_obs:
        return {"n_windows": 0, "ic_mean": None, "ic_std": None, "ic_ir": None, "ic_neg_rate": None}

    valid.sort(key=lambda x: x[0])
    start_d = valid[0][0]
    end_d = valid[-1][0]

    window_ics: list[float] = []
    cursor = start_d
    while True:
        window_end = cursor + pd.DateOffset(months=window_months)
        window_end_date = window_end.date()
        if window_end_date > end_d:
            break

        slice_ = [(t, r) for d, t, r in valid if cursor <= d <= window_end_date]
        if len(slice_) >= min_obs:
            xs = [x[0] for x in slice_]
            ys = [x[1] for x in slice_]
            from scipy import stats

            rho, _ = stats.spearmanr(xs, ys)
            if not np.isnan(rho):
                window_ics.append(float(rho))

        cursor = (cursor + pd.DateOffset(months=step_months)).date()

    if not window_ics:
        return {"n_windows": 0, "ic_mean": None, "ic_std": None, "ic_ir": None, "ic_neg_rate": None}

    ics = np.array(window_ics)
    mean = float(np.mean(ics))
    std = float(np.std(ics, ddof=1)) if len(ics) > 1 else 0.0
    ir = float(mean / std) if std > 0 else None
    neg_rate = float((ics < 0).mean())
    return {
        "n_windows": len(window_ics),
        "ic_mean": round(mean, 4),
        "ic_std": round(std, 4),
        "ic_ir": round(ir, 4) if ir is not None else None,
        "ic_neg_rate": round(neg_rate, 4),
    }


def compute_rolling_ic(
    macro_long: pd.DataFrame,
    temp_df: pd.DataFrame,
    window_months: int = 36,
    step_months: int = 3,
) -> dict[str, dict[str, dict]]:
    """Compute rolling OOS IC per market per horizon.

    Returns: {market: {horizon: {"ic_mean": ..., "ic_ir": ..., ...}}}
    """
    if not SCIPY_AVAILABLE:
        empty: dict = {"n_windows": 0, "ic_mean": None, "ic_std": None, "ic_ir": None, "ic_neg_rate": None}
        return {m: {h: empty for h in FORWARD_HORIZONS} for m in MARKETS}

    wide = macro_long.pivot_table(index="date", columns="indicator", values="value").sort_index()
    wide.index = pd.to_datetime(wide.index)

    tdf = temp_df.copy()
    tdf["date"] = pd.to_datetime(tdf["date"])

    result: dict[str, dict[str, dict]] = {}

    for market, idx_ticker in INDEX_MAP.items():
        market_result: dict[str, dict] = {}

        if idx_ticker not in wide.columns:
            empty: dict = {"n_windows": 0, "ic_mean": None, "ic_std": None, "ic_ir": None, "ic_neg_rate": None}
            for h in FORWARD_HORIZONS:
                market_result[h] = empty
            result[market] = market_result
            continue

        prices = wide[idx_ticker].dropna()
        sub = tdf[tdf["market"] == market].copy()

        horizon_pairs: dict[str, list[tuple[date, float, float | None]]] = {h: [] for h in FORWARD_HORIZONS}

        for _, row in sub.iterrows():
            t = pd.Timestamp(row["date"])
            if t not in prices.index:
                continue
            t_pos = prices.index.get_loc(t)
            n_prices = len(prices.index)
            current = prices.iloc[t_pos]

            for label, days in FORWARD_HORIZONS.items():
                fwd_pos = t_pos + days
                if fwd_pos >= n_prices:
                    continue
                fwd_return = float(prices.iloc[fwd_pos] / current - 1.0)
                horizon_pairs[label].append((t.date(), float(row["overall"]), fwd_return))

        for horizon in FORWARD_HORIZONS:
            market_result[horizon] = _rolling_ic_single(horizon_pairs[horizon], window_months, step_months)

        result[market] = market_result

    return result


def compute_config_hash(weights_path: Path, transform_dir: Path | None = None) -> str:
    """Compute SHA256 hash of weights.yaml + all transform/*.py files."""
    hasher = hashlib.sha256()

    with open(weights_path, "rb") as f:
        hasher.update(f.read())

    if transform_dir is None:
        transform_dir = weights_path.parent.parent / "src" / "finsynapse" / "transform"

    for py_file in sorted(transform_dir.glob("*.py")):
        with open(py_file, "rb") as f:
            hasher.update(py_file.name.encode())
            hasher.update(f.read())

    return hasher.hexdigest()[:12]


def _build_metrics_dict(
    pivot_dir_rate: float,
    pivot_strict_rate: float,
    per_market_pivots: dict,
    forward_rho: dict,
    rolling_ic: dict,
    regime_ic: dict | None = None,
    bootstrap: dict | None = None,
) -> tuple[dict, dict]:
    """Build flat metrics dict + per_market dict from computed values."""

    metrics: dict[str, float | None] = {}
    metrics["pivot_directional_rate"] = pivot_dir_rate
    metrics["pivot_strict_rate"] = pivot_strict_rate

    per_market: dict[str, dict[str, Any]] = {}
    for mkt in MARKETS:
        pm: dict[str, Any] = {
            "directional_rate": per_market_pivots.get(mkt, {}).get("directional_rate", 0),
            "strict_rate": per_market_pivots.get(mkt, {}).get("strict_rate", 0),
            "mean_reversion_strength": {},
            "oos_ic": {},
            "regime_ic": {},
            "bootstrap": {},
        }
        for h in FORWARD_HORIZONS:
            rho = forward_rho.get(mkt, {}).get(h)
            mrs = None if rho is None else round(-rho, 4)
            pm["mean_reversion_strength"][h] = mrs
            metrics[f"mean_reversion_strength.{h}.{mkt}"] = mrs

            oos = rolling_ic.get(mkt, {}).get(h, {})
            ic_mean = oos.get("ic_mean")
            pm["oos_ic"][h] = oos
            metrics[f"oos_ic_mean.{h}.{mkt}"] = ic_mean
            metrics[f"oos_ic_ir.{h}.{mkt}"] = oos.get("ic_ir")

        # Regime-stratified IC
        if regime_ic:
            pm["regime_ic"] = regime_ic.get(mkt, {})
            for regime in ["bull", "bear", "sideways"]:
                ri = pm["regime_ic"].get(regime, {})
                for h in FORWARD_HORIZONS:
                    rh = ri.get(h, {})
                    val = rh.get("ic_mean")
                    metrics[f"regime_ic_{regime}.{h}.{mkt}"] = val

        # Bootstrap CI
        if bootstrap:
            pm["bootstrap"] = bootstrap.get(mkt, {})
            for h in FORWARD_HORIZONS:
                bh = pm["bootstrap"].get(h, {})
                metrics[f"bootstrap_ic_ci_low.{h}.{mkt}"] = bh.get("ic_ci_low")
                metrics[f"bootstrap_ic_ci_high.{h}.{mkt}"] = bh.get("ic_ci_high")

        per_market[mkt] = pm

    return metrics, per_market


# ── regime classification ───────────────────────────────────────────────────


def _classify_regimes(
    prices: pd.Series, ma_window: int = 200, drawdown_threshold: float = 0.20
) -> pd.Series:
    """Classify each date as bull / bear / sideways.

    - bull:  price >= 200d MA AND not in >20% drawdown
    - bear:  price < 200d MA OR drawdown >20% from prior peak
    - sideways: everything else
    """
    ma = prices.rolling(window=ma_window, min_periods=ma_window).mean()
    peak = prices.expanding().max()
    drawdown = (prices - peak) / peak

    regime = pd.Series("sideways", index=prices.index)
    above_ma = prices >= ma
    not_deep_dd = drawdown > -drawdown_threshold

    regime[above_ma & not_deep_dd] = "bull"
    regime[(~above_ma) | (drawdown <= -drawdown_threshold)] = "bear"

    return regime


def compute_regime_stratified_ic(
    macro_long: pd.DataFrame,
    temp_df: pd.DataFrame,
) -> dict[str, dict[str, dict[str, dict]]]:
    """Compute Spearman rho (IC) within each market regime.

    Returns: {market: {regime: {horizon: {"ic_mean": ..., "n": ...}}}}
    """
    if not SCIPY_AVAILABLE:
        empty = {h: {"ic_mean": None, "n": 0} for h in FORWARD_HORIZONS}
        empty_regime = {"bull": empty, "bear": empty, "sideways": empty}
        return {m: empty_regime for m in MARKETS}

    wide = macro_long.pivot_table(index="date", columns="indicator", values="value").sort_index()
    wide.index = pd.to_datetime(wide.index)

    tdf = temp_df.copy()
    tdf["date"] = pd.to_datetime(tdf["date"])

    result: dict[str, dict[str, dict[str, dict]]] = {}

    for market, idx_ticker in INDEX_MAP.items():
        if idx_ticker not in wide.columns:
            empty = {h: {"ic_mean": None, "n": 0} for h in FORWARD_HORIZONS}
            result[market] = {"bull": empty, "bear": empty, "sideways": empty}
            continue

        prices = wide[idx_ticker].dropna()
        regimes = _classify_regimes(prices)
        sub = tdf[tdf["market"] == market].copy()

        # Collect (date, temperature, forward_return) per horizon
        horizon_data: dict[str, list[tuple[date, float, float, str]]] = {h: [] for h in FORWARD_HORIZONS}

        for _, row in sub.iterrows():
            t = pd.Timestamp(row["date"])
            if t not in prices.index or t not in regimes.index:
                continue
            t_pos = prices.index.get_loc(t)
            n_prices = len(prices.index)
            current = prices.iloc[t_pos]
            regime = regimes.loc[t]

            for label, days in FORWARD_HORIZONS.items():
                fwd_pos = t_pos + days
                if fwd_pos >= n_prices:
                    continue
                fwd_return = float(prices.iloc[fwd_pos] / current - 1.0)
                horizon_data[label].append((t.date(), float(row["overall"]), fwd_return, regime))

        market_result: dict[str, dict[str, dict]] = {}
        for regime in ["bull", "bear", "sideways"]:
            regime_result: dict[str, dict] = {}
            for horizon in FORWARD_HORIZONS:
                xs = [x[1] for x in horizon_data[horizon] if x[3] == regime]
                ys = [x[2] for x in horizon_data[horizon] if x[3] == regime]
                if len(xs) < 30:
                    regime_result[horizon] = {"ic_mean": None, "n": len(xs)}
                    continue
                from scipy import stats

                rho, _ = stats.spearmanr(xs, ys)
                regime_result[horizon] = {
                    "ic_mean": round(float(rho), 4) if not np.isnan(rho) else None,
                    "n": len(xs),
                }
            market_result[regime] = regime_result
        result[market] = market_result

    return result


# ── bootstrap CI ────────────────────────────────────────────────────────────


def _bootstrap_confidence(
    xs: np.ndarray,
    ys: np.ndarray,
    n_bootstrap: int = 500,
    alpha: float = 0.05,
) -> dict:
    """Bootstrap 95% CI for Spearman rho.

    Returns {"ic_mean": ..., "ic_ci_low": ..., "ic_ci_high": ..., "n": ...}.
    """
    if len(xs) < 30:
        return {"ic_mean": None, "ic_ci_low": None, "ic_ci_high": None, "n": len(xs)}

    n = len(xs)
    rng = np.random.default_rng(42)
    rhos: list[float] = []
    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        bx, by = xs[idx], ys[idx]
        rho, _ = _scipy_stats.spearmanr(bx, by)
        if not np.isnan(rho):
            rhos.append(float(rho))

    if not rhos:
        return {"ic_mean": None, "ic_ci_low": None, "ic_ci_high": None, "n": len(xs)}

    rhos_arr = np.array(rhos)
    ci_low = float(np.percentile(rhos_arr, alpha / 2 * 100))
    ci_high = float(np.percentile(rhos_arr, (1 - alpha / 2) * 100))
    return {
        "ic_mean": round(float(np.mean(rhos_arr)), 4),
        "ic_ci_low": round(ci_low, 4),
        "ic_ci_high": round(ci_high, 4),
        "n": len(xs),
    }


def compute_bootstrap_ci(
    macro_long: pd.DataFrame,
    temp_df: pd.DataFrame,
    n_bootstrap: int = 500,
) -> dict[str, dict[str, dict]]:
    """Bootstrap 95% CI for Spearman rho per market per horizon.

    Returns: {market: {horizon: {"ic_mean": ..., "ic_ci_low": ..., "ic_ci_high": ...}}}
    """
    if not SCIPY_AVAILABLE:
        empty = {h: {"ic_mean": None, "ic_ci_low": None, "ic_ci_high": None, "n": 0} for h in FORWARD_HORIZONS}
        return {m: empty for m in MARKETS}

    wide = macro_long.pivot_table(index="date", columns="indicator", values="value").sort_index()
    wide.index = pd.to_datetime(wide.index)

    tdf = temp_df.copy()
    tdf["date"] = pd.to_datetime(tdf["date"])

    result: dict[str, dict[str, dict]] = {}

    for market, idx_ticker in INDEX_MAP.items():
        market_result: dict[str, dict] = {}

        if idx_ticker not in wide.columns:
            for h in FORWARD_HORIZONS:
                market_result[h] = {"ic_mean": None, "ic_ci_low": None, "ic_ci_high": None, "n": 0}
            result[market] = market_result
            continue

        prices = wide[idx_ticker].dropna()
        sub = tdf[tdf["market"] == market].copy()

        horizon_pairs: dict[str, tuple[list[float], list[float]]] = {h: ([], []) for h in FORWARD_HORIZONS}

        for _, row in sub.iterrows():
            t = pd.Timestamp(row["date"])
            if t not in prices.index:
                continue
            t_pos = prices.index.get_loc(t)
            n_prices = len(prices.index)
            current = prices.iloc[t_pos]

            for label, days in FORWARD_HORIZONS.items():
                fwd_pos = t_pos + days
                if fwd_pos >= n_prices:
                    continue
                fwd_return = float(prices.iloc[fwd_pos] / current - 1.0)
                horizon_pairs[label][0].append(float(row["overall"]))
                horizon_pairs[label][1].append(fwd_return)

        for horizon in FORWARD_HORIZONS:
            xs_arr = np.array(horizon_pairs[horizon][0])
            ys_arr = np.array(horizon_pairs[horizon][1])
            market_result[horizon] = _bootstrap_confidence(xs_arr, ys_arr, n_bootstrap)

        result[market] = market_result

    return result
