"""Static JSON API endpoints published alongside the dashboard.

Output layout under `dist/api/`:

  manifest.json              schema version + endpoint inventory + asof
  temperature_latest.json    per-market latest overall + sub-temps
  temperature_history.json.gz long time series (gzipped, full history)
  indicators_latest.json     per-indicator latest values + pct/source/staleness
  divergence_latest.json     active divergence signals (last 90 days)

Consumers:
  - external AI agents wanting the latest reading without HTML scraping
  - downstream tools / notebooks that want a stable JSON contract

Schema versioning: adding fields is non-breaking; changing existing field
names, shapes, or semantics is a major version bump.
"""

from __future__ import annotations

import gzip
import json
import math
from numbers import Real
from pathlib import Path
from typing import Any

import pandas as pd

from finsynapse.dashboard.data import MARKETS, DashboardData

API_SCHEMA_VERSION = "2.0.0"

ENDPOINT_DESCRIPTIONS: dict[str, str] = {
    "manifest.json": "Schema version, per-market as-of dates, build time, and endpoint inventory.",
    "temperature_latest.json": "Per-market latest temperature: overall + valuation/sentiment/liquidity sub-temps + 1-week change attribution.",
    "temperature_history.json.gz": "Per-market full daily history of overall + sub-temps. Gzipped JSON.",
    "indicators_latest.json": "Latest available value for each factor, with rolling percentiles (5y/10y), source, and staleness.",
    "divergence_latest.json": "Active divergence signals from the last 90 days, sorted by product strength.",
}


def build_manifest(
    asof: str | None,
    endpoints: list[str],
    *,
    generated_at_utc: str | None = None,
    market_asof: dict[str, str | None] | None = None,
    latest_complete_date: dict[str, str | None] | None = None,
    raw_temperature_asof: str | None = None,
) -> dict[str, Any]:
    """Assemble the manifest payload describing what's published and when."""
    return {
        "schema_version": API_SCHEMA_VERSION,
        "asof": asof,
        "market_asof": market_asof or {},
        "latest_complete_date": latest_complete_date or {},
        "raw_temperature_asof": raw_temperature_asof,
        "generated_at_utc": generated_at_utc or pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endpoints": {
            name: {"path": f"api/{name}", "description": ENDPOINT_DESCRIPTIONS.get(name, "")} for name in endpoints
        },
    }


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            out = float(value.strip())
        except ValueError as exc:
            raise TypeError(f"Expected numeric scalar, got {type(value).__name__}") from exc
    elif isinstance(value, bool):
        raise TypeError("Expected numeric scalar, got bool")
    elif isinstance(value, Real):
        if pd.isna(value):
            return None
        out = float(value)
    else:
        try:
            if pd.isna(value) is True:
                return None
        except (TypeError, ValueError):
            pass
        raise TypeError(f"Expected numeric scalar, got {type(value).__name__}")
    if pd.isna(out):
        return None
    if not math.isfinite(out):
        raise TypeError("Expected finite numeric scalar")
    return out


def _build_temperature_latest(data: DashboardData) -> dict[str, Any]:
    latest = data.latest_per_market()
    complete = data.latest_complete_date()
    market_asof = data.market_asof()
    raw_asof = pd.to_datetime(data.temperature["date"].max()).strftime("%Y-%m-%d")
    effective = data.effective_asof()
    asof = effective.strftime("%Y-%m-%d") if effective is not None else None

    markets_payload: dict[str, Any] = {}
    for market in MARKETS:
        if market not in latest:
            markets_payload[market] = {"available": False}
            continue
        row = latest[market]
        markets_payload[market] = {
            "available": True,
            "asof": pd.to_datetime(row["date"]).strftime("%Y-%m-%d"),
            "latest_complete_date": complete.get(market),
            "overall": _safe_float(row.get("overall")),
            "sub_temperatures": {
                "valuation": _safe_float(row.get("valuation")),
                "sentiment": _safe_float(row.get("sentiment")),
                "liquidity": _safe_float(row.get("liquidity")),
            },
            "change_1w": {
                "overall": _safe_float(row.get("overall_change_1w")),
                "attribution": {
                    "valuation": _safe_float(row.get("valuation_contribution_1w")),
                    "sentiment": _safe_float(row.get("sentiment_contribution_1w")),
                    "liquidity": _safe_float(row.get("liquidity_contribution_1w")),
                },
            },
            "data_quality": row.get("data_quality", "ok"),
            "subtemp_completeness": int(row["subtemp_completeness"])
            if "subtemp_completeness" in row and not pd.isna(row.get("subtemp_completeness"))
            else None,
            "conf_ok": int(row["conf_ok"]) if "conf_ok" in row and not pd.isna(row.get("conf_ok")) else None,
            "is_complete": bool(row.get("is_complete", False)),
        }
    return {
        "schema_version": API_SCHEMA_VERSION,
        "asof": asof,
        "market_asof": market_asof,
        "latest_complete_date": complete,
        "raw_temperature_asof": raw_asof,
        "markets": markets_payload,
    }


def _build_indicators_latest(data: DashboardData) -> dict[str, Any]:
    if data.percentile.empty:
        return {"schema_version": API_SCHEMA_VERSION, "asof": None, "raw_percentile_asof": None, "indicators": []}
    pct = data.percentile.copy()
    pct["date"] = pd.to_datetime(pct["date"])
    raw_asof = pct["date"].max()
    api_asof = data.effective_asof()
    api_asof = api_asof.normalize() if api_asof is not None else raw_asof.normalize()
    snap = (
        pct.sort_values(["indicator", "date"]).drop_duplicates(subset="indicator", keep="last").sort_values("indicator")
    )
    sources: dict[str, str | None] = {}
    if not data.macro.empty and {"indicator", "date", "source"}.issubset(data.macro.columns):
        macro = data.macro[["indicator", "date", "source"]].copy()
        macro["date"] = pd.to_datetime(macro["date"])
        source_rows = macro.sort_values(["indicator", "date"]).drop_duplicates(subset="indicator", keep="last")
        sources = {
            str(row["indicator"]): None if pd.isna(row["source"]) else str(row["source"])
            for _, row in source_rows.iterrows()
        }
    indicators: list[dict[str, Any]] = []
    for _, row in snap.iterrows():
        last_seen = pd.to_datetime(row["date"]).normalize()
        indicators.append(
            {
                "indicator": str(row["indicator"]),
                "value": _safe_float(row.get("value")),
                "percentile_5y": _safe_float(row.get("pct_5y")),
                "percentile_10y": _safe_float(row.get("pct_10y")),
                "last_seen": last_seen.strftime("%Y-%m-%d"),
                "days_stale": max(0, int((api_asof - last_seen).days)),
                "source": sources.get(str(row["indicator"])),
            }
        )
    return {
        "schema_version": API_SCHEMA_VERSION,
        "asof": api_asof.strftime("%Y-%m-%d"),
        "raw_percentile_asof": raw_asof.strftime("%Y-%m-%d"),
        "indicators": indicators,
    }


def _build_divergence_latest(data: DashboardData, window_days: int = 90) -> dict[str, Any]:
    if data.divergence.empty:
        return {"schema_version": API_SCHEMA_VERSION, "window_days": window_days, "signals": []}
    df = data.divergence.copy()
    df["date"] = pd.to_datetime(df["date"])
    cutoff = df["date"].max() - pd.Timedelta(days=window_days)
    active = df[(df["is_divergent"]) & (df["date"] >= cutoff)].sort_values("strength", ascending=False)
    # De-dup by pair, keep the strongest occurrence (mirrors dashboard logic).
    active = active.drop_duplicates(subset="pair_name", keep="first")
    signals = [
        {
            "date": row["date"].strftime("%Y-%m-%d"),
            "pair": str(row["pair_name"]),
            "strength": _safe_float(row.get("strength")),
            "description": str(row.get("description", "")),
            "a_change_pct": _safe_float(row["a_change"]) * 100 if not pd.isna(row.get("a_change")) else None,
            "b_change_pct": _safe_float(row["b_change"]) * 100 if not pd.isna(row.get("b_change")) else None,
        }
        for _, row in active.iterrows()
    ]
    return {
        "schema_version": API_SCHEMA_VERSION,
        "window_days": window_days,
        "asof": active["date"].max().strftime("%Y-%m-%d") if not active.empty else None,
        "signals": signals,
    }


HISTORY_COLUMNS = ("overall", "valuation", "sentiment", "liquidity")


def _build_temperature_history(data: DashboardData) -> dict[str, Any]:
    df = data.temperature.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["market", "date"])
    markets_payload: dict[str, list[dict[str, Any]]] = {}
    for market in MARKETS:
        sub = df[df["market"] == market]
        if sub.empty:
            continue
        rows = []
        for _, row in sub.iterrows():
            entry = {"date": row["date"].strftime("%Y-%m-%d")}
            for col in HISTORY_COLUMNS:
                if col in row:
                    entry[col] = _safe_float(row[col])
            rows.append(entry)
        markets_payload[market] = rows
    return {
        "schema_version": API_SCHEMA_VERSION,
        "asof": data.effective_asof().strftime("%Y-%m-%d") if data.effective_asof() is not None else None,
        "market_asof": data.market_asof(),
        "raw_temperature_asof": pd.to_datetime(data.temperature["date"].max()).strftime("%Y-%m-%d"),
        "markets": markets_payload,
    }


def write_all(data: DashboardData, out_dir: Path, *, generated_at_utc: str | None = None) -> list[Path]:
    api_dir = out_dir / "api"
    api_dir.mkdir(parents=True, exist_ok=True)
    if data.temperature.empty:
        return []
    written: list[Path] = []

    temp_latest = _build_temperature_latest(data)
    p = api_dir / "temperature_latest.json"
    p.write_text(json.dumps(temp_latest, indent=2, ensure_ascii=False))
    written.append(p)

    indicators = _build_indicators_latest(data)
    if indicators["indicators"]:
        p = api_dir / "indicators_latest.json"
        p.write_text(json.dumps(indicators, indent=2, ensure_ascii=False))
        written.append(p)

    divergence = _build_divergence_latest(data)
    if divergence["signals"]:
        p = api_dir / "divergence_latest.json"
        p.write_text(json.dumps(divergence, indent=2, ensure_ascii=False))
        written.append(p)

    history = _build_temperature_history(data)
    if history["markets"]:
        p = api_dir / "temperature_history.json.gz"
        p.write_bytes(gzip.compress(json.dumps(history, ensure_ascii=False).encode("utf-8")))
        written.append(p)

    asof = temp_latest["asof"]
    endpoints = [p.name for p in written] + ["manifest.json"]
    manifest = build_manifest(
        asof=asof,
        endpoints=endpoints,
        generated_at_utc=generated_at_utc,
        market_asof=temp_latest["market_asof"],
        latest_complete_date=temp_latest["latest_complete_date"],
        raw_temperature_asof=temp_latest["raw_temperature_asof"],
    )
    mp = api_dir / "manifest.json"
    mp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    written.append(mp)
    return written
