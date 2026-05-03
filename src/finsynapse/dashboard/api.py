"""Static JSON API endpoints published alongside the dashboard.

Output layout under `dist/api/`:

  manifest.json              schema version + endpoint inventory + asof
  temperature_latest.json    per-market latest overall + sub-temps
  temperature_history.json.gz long time series (gzipped, full history)
  indicators_latest.json     all underlying factor latest values + pct
  divergence_latest.json     active divergence signals (last 90 days)

Consumers:
  - external AI agents wanting the latest reading without HTML scraping
  - downstream tools / notebooks that want a stable JSON contract

Schema versioning: bump `API_SCHEMA_VERSION` whenever a field is removed
or its meaning changes. Adding new fields is non-breaking.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import pandas as pd

from finsynapse.dashboard.data import MARKETS, DashboardData

API_SCHEMA_VERSION = "1.0.0"

ENDPOINT_DESCRIPTIONS: dict[str, str] = {
    "manifest.json": "Schema version, asof date, and inventory of all endpoints.",
    "temperature_latest.json": "Per-market latest temperature: overall + valuation/sentiment/liquidity sub-temps + 1-week change attribution.",
    "temperature_history.json.gz": "Per-market full daily history of overall + sub-temps. Gzipped JSON.",
    "indicators_latest.json": "All underlying factor latest values and rolling percentiles (5y/10y).",
    "divergence_latest.json": "Active divergence signals from the last 90 days, sorted by strength.",
}


def build_manifest(asof: str, endpoints: list[str]) -> dict[str, Any]:
    """Assemble the manifest payload describing what's published and when."""
    return {
        "schema_version": API_SCHEMA_VERSION,
        "asof": asof,
        "generated_at_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endpoints": {
            name: {"path": f"api/{name}", "description": ENDPOINT_DESCRIPTIONS.get(name, "")} for name in endpoints
        },
    }


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return float(value)


def _build_temperature_latest(data: DashboardData) -> dict[str, Any]:
    latest = data.latest_per_market()
    complete = data.latest_complete_date()
    asof = pd.to_datetime(data.temperature["date"].max()).strftime("%Y-%m-%d")

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
            "is_complete": bool(row.get("is_complete", False)),
        }
    return {
        "schema_version": API_SCHEMA_VERSION,
        "asof": asof,
        "markets": markets_payload,
    }


def write_all(data: DashboardData, out_dir: Path) -> list[Path]:
    api_dir = out_dir / "api"
    api_dir.mkdir(parents=True, exist_ok=True)
    if data.temperature.empty:
        return []
    written: list[Path] = []

    temp_latest = _build_temperature_latest(data)
    p = api_dir / "temperature_latest.json"
    p.write_text(json.dumps(temp_latest, indent=2, ensure_ascii=False))
    written.append(p)

    asof = temp_latest["asof"]
    endpoints = [p.name for p in written] + ["manifest.json"]
    manifest = build_manifest(asof=asof, endpoints=endpoints)
    mp = api_dir / "manifest.json"
    mp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    written.append(mp)
    return written
