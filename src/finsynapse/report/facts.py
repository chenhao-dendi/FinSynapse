"""Deterministic fact assembly for the daily macro brief."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from finsynapse.dashboard.data import MARKETS, load


@dataclass
class FactPack:
    """Numerical snapshot the brief is built from. All numbers are real."""

    asof: str
    markets: dict[str, dict] = field(default_factory=dict)
    divergences: list[dict] = field(default_factory=list)
    health_warn_count: int = 0
    health_fail_count: int = 0
    notable_indicators: list[dict] = field(default_factory=list)


def _zone(v: float | None) -> str:
    if v is None or pd.isna(v):
        return "unknown"
    if v < 30:
        return "cold"
    if v < 70:
        return "mid"
    return "hot"


def _zone_emoji(z: str) -> str:
    return {"cold": "🧊", "mid": "🌤", "hot": "🔥"}.get(z, "❔")


def assemble_facts() -> FactPack:
    data = load()
    if data.temperature.empty:
        raise RuntimeError("No silver data — run `finsynapse transform run --layer all` first.")

    latest = data.latest_per_market()
    asof_dates = [pd.to_datetime(row["date"]) for row in latest.values()]
    asof = (max(asof_dates) if asof_dates else data.asof()).date().isoformat()
    fp = FactPack(asof=asof)

    for market in MARKETS:
        if market not in latest:
            continue
        row = latest[market]
        fp.markets[market] = {
            "date": pd.to_datetime(row["date"]).date().isoformat(),
            "overall": float(row["overall"]) if not pd.isna(row["overall"]) else None,
            "overall_zone": _zone(row.get("overall")),
            "valuation": None if pd.isna(row.get("valuation")) else float(row["valuation"]),
            "sentiment": None if pd.isna(row.get("sentiment")) else float(row["sentiment"]),
            "liquidity": None if pd.isna(row.get("liquidity")) else float(row["liquidity"]),
            "overall_change_1w": (None if pd.isna(row.get("overall_change_1w")) else float(row["overall_change_1w"])),
            "valuation_contribution_1w": (
                None if pd.isna(row.get("valuation_contribution_1w")) else float(row["valuation_contribution_1w"])
            ),
            "sentiment_contribution_1w": (
                None if pd.isna(row.get("sentiment_contribution_1w")) else float(row["sentiment_contribution_1w"])
            ),
            "liquidity_contribution_1w": (
                None if pd.isna(row.get("liquidity_contribution_1w")) else float(row["liquidity_contribution_1w"])
            ),
            "data_quality": str(row.get("data_quality", "ok")),
        }

    # Recent divergences (last 5 trading days, ranked by strength). Limit to
    # the top 6 to keep prompts tight; the model gets to pick which to discuss.
    if not data.divergence.empty:
        div = data.divergence[data.divergence["is_divergent"]].copy()
        div["date"] = pd.to_datetime(div["date"])
        cutoff = div["date"].max() - pd.Timedelta(days=5)
        recent = div[div["date"] >= cutoff].nlargest(6, "strength")
        fp.divergences = [
            {
                "date": d["date"].date().isoformat(),
                "pair": d["pair_name"],
                "a_change_pct": float(d["a_change"]) * 100,
                "b_change_pct": float(d["b_change"]) * 100,
                "strength": float(d["strength"]),
                "description": d["description"],
            }
            for _, d in recent.iterrows()
        ]

    # Notable indicators: top/bottom percentile readings on the latest available date.
    if not data.percentile.empty:
        pct = data.percentile.copy()
        pct["date"] = pd.to_datetime(pct["date"])
        latest_dt = pct["date"].max()
        snap = pct[pct["date"] == latest_dt].dropna(subset=["pct_10y"])
        # Keep extremes (>=85 or <=15) — those are the percentile-wise interesting ones.
        extreme = snap[(snap["pct_10y"] >= 85) | (snap["pct_10y"] <= 15)]
        fp.notable_indicators = [
            {
                "indicator": r["indicator"],
                "value": float(r["value"]),
                "pct_10y": float(r["pct_10y"]),
            }
            for _, r in extreme.sort_values("pct_10y", ascending=False).head(8).iterrows()
        ]

    if not data.health.empty:
        h = data.health
        fp.health_fail_count = int((h["severity"] == "fail").sum())
        fp.health_warn_count = int((h["severity"] == "warn").sum())

    return fp
