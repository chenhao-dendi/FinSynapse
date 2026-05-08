"""Build or verify the eval silver fixture manifest.

The eval fixture is the fixed historical dataset behind the champion-
challenger gate. This script makes its audit metadata reproducible instead of
hand-maintained.

Usage:
    uv run python scripts/build_eval_fixture_manifest.py --verify
    uv run python scripts/build_eval_fixture_manifest.py --write
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

DEFAULT_FIXTURE_DIR = Path("tests/fixtures/eval_silver_2026Q1")
DEFAULT_PIVOTS_PATH = Path("scripts/backtest_pivots.yaml")
DEFAULT_WEIGHTS_PATH = Path("config/weights.yaml")
DEFAULT_MANIFEST_NAME = "MANIFEST.json"
PARQUET_FILES = ("macro_daily.parquet", "percentile_daily.parquet", "temperature_daily.parquet")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest(
    fixture_dir: Path,
    pivots_path: Path,
    *,
    created: str,
    source_commit: str,
    weights_path: Path = DEFAULT_WEIGHTS_PATH,
    source_data: str = "data/silver/{macro_daily,percentile_daily,temperature_daily}.parquet",
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "fixture_id": fixture_dir.name,
        "created": created,
        "source_commit": source_commit,
        "source_data": source_data,
        "date_window": _date_window(fixture_dir),
        "files": {},
        "pivot_coverage": _pivot_coverage(fixture_dir, pivots_path),
        "indicator_pivot_coverage": _indicator_pivot_coverage(fixture_dir, pivots_path, weights_path),
    }

    for filename in PARQUET_FILES:
        manifest["files"][filename] = _file_manifest(fixture_dir / filename)

    return manifest


def _date_window(fixture_dir: Path) -> dict[str, str]:
    starts: list[str] = []
    ends: list[str] = []
    for filename in ("macro_daily.parquet", "percentile_daily.parquet"):
        info = _date_info(pd.read_parquet(fixture_dir / filename))
        starts.append(info["date_min"])
        ends.append(info["date_max"])
    return {"start": min(starts), "end": max(ends)}


def _file_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)

    df = pd.read_parquet(path)
    info: dict[str, Any] = {
        "sha256": sha256(path),
        "rows": len(df),
        **_date_info(df),
        "columns": list(df.columns),
    }
    if "indicator" in df.columns:
        info["indicators"] = sorted(df["indicator"].astype(str).unique())
    if "market" in df.columns:
        info["markets"] = sorted(df["market"].astype(str).unique())
    return info


def _date_info(df: pd.DataFrame) -> dict[str, Any]:
    if "date" not in df.columns:
        raise KeyError("fixture parquet missing `date` column")
    dates = pd.to_datetime(df["date"])
    return {
        "date_min": dates.min().date().isoformat(),
        "date_max": dates.max().date().isoformat(),
        "n_dates": int(dates.nunique()),
    }


def _pivot_coverage(fixture_dir: Path, pivots_path: Path) -> dict[str, Any]:
    pivots = yaml.safe_load(pivots_path.read_text())["pivots"]
    temp = pd.read_parquet(fixture_dir / "temperature_daily.parquet")
    temp["date"] = pd.to_datetime(temp["date"])

    covered = []
    missing = []
    for pivot in pivots:
        target = pd.Timestamp(pivot["date"])
        sub = temp[(temp["market"] == pivot["market"]) & (temp["date"] <= target)].sort_values("date").tail(1)
        if sub.empty or pd.isna(sub.iloc[0]["overall"]):
            missing.append(pivot)
        else:
            covered.append(pivot)

    return {
        "pivots_path": str(pivots_path),
        "total": len(pivots),
        "covered": len(covered),
        "missing": len(missing),
        "by_market": dict(Counter(p["market"] for p in covered)),
    }


def _indicator_pivot_coverage(fixture_dir: Path, pivots_path: Path, weights_path: Path) -> dict[str, Any]:
    weights = yaml.safe_load(weights_path.read_text())
    indicators_by_market = _weighted_indicators_by_market(weights)
    pivots = yaml.safe_load(pivots_path.read_text())["pivots"]

    macro = pd.read_parquet(fixture_dir / "macro_daily.parquet")
    pct = pd.read_parquet(fixture_dir / "percentile_daily.parquet")
    macro["date"] = pd.to_datetime(macro["date"])
    pct["date"] = pd.to_datetime(pct["date"])

    total = 0
    available = 0
    by_market: dict[str, dict[str, int]] = {}
    by_indicator: dict[str, dict[str, int]] = {}
    missing_required_percentiles: list[dict[str, Any]] = []

    for pivot in pivots:
        market = pivot["market"]
        target = pd.Timestamp(pivot["date"])
        for indicator, window in indicators_by_market.get(market, {}).items():
            total += 1
            by_market.setdefault(market, {"available": 0, "total": 0})
            by_market[market]["total"] += 1
            by_indicator.setdefault(indicator, {"available": 0, "total": 0})
            by_indicator[indicator]["total"] += 1

            raw_latest = _latest_indicator_row(macro, indicator, target)
            pct_latest = _latest_indicator_row(pct, indicator, target)
            pct_available = not pct_latest.empty and pd.notna(pct_latest.iloc[0].get(window))

            if pct_available:
                available += 1
                by_market[market]["available"] += 1
                by_indicator[indicator]["available"] += 1
                continue

            raw_date = _row_date(raw_latest)
            pct_date = _row_date(pct_latest)
            missing_required_percentiles.append(
                {
                    "pivot_label": pivot["label"],
                    "pivot_date": pivot["date"],
                    "market": market,
                    "indicator": indicator,
                    "required_window": window,
                    "raw_latest_date": raw_date,
                    "raw_lag_days": _lag_days(target, raw_date),
                    "pct_latest_date": pct_date,
                    "pct_lag_days": _lag_days(target, pct_date),
                    "reason": "no_percentile_row" if pct_latest.empty else f"{window}_is_null",
                }
            )

    return {
        "weights_path": str(weights_path),
        "pivots_path": str(pivots_path),
        "total_checks": total,
        "available_checks": available,
        "missing_checks": total - available,
        "by_market": by_market,
        "by_indicator": by_indicator,
        "missing_required_percentiles": missing_required_percentiles,
    }


def _weighted_indicators_by_market(weights: dict[str, Any]) -> dict[str, dict[str, str]]:
    default_window = weights.get("percentile_window", "pct_10y")
    by_market: dict[str, dict[str, str]] = {}
    for block_name, indicators in weights.get("indicator_weights", {}).items():
        market = block_name.split("_", 1)[0]
        by_market.setdefault(market, {})
        for indicator, meta in indicators.items():
            by_market[market][indicator] = meta.get("window", default_window)
    return {market: dict(sorted(indicators.items())) for market, indicators in sorted(by_market.items())}


def _latest_indicator_row(df: pd.DataFrame, indicator: str, target: pd.Timestamp) -> pd.DataFrame:
    sub = df[(df["indicator"] == indicator) & (df["date"] <= target)].sort_values("date").tail(1)
    return sub


def _row_date(row: pd.DataFrame) -> str | None:
    if row.empty:
        return None
    return pd.Timestamp(row.iloc[0]["date"]).date().isoformat()


def _lag_days(target: pd.Timestamp, date_iso: str | None) -> int | None:
    if date_iso is None:
        return None
    return int((target.date() - pd.Timestamp(date_iso).date()).days)


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def dump_manifest(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"


def _main() -> int:
    parser = argparse.ArgumentParser(description="Build or verify eval fixture MANIFEST.json")
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    parser.add_argument("--pivots", type=Path, default=DEFAULT_PIVOTS_PATH)
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS_PATH)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--created", default=None, help="Required for --write unless manifest already exists")
    parser.add_argument("--source-commit", default=None, help="Required for --write unless manifest already exists")
    parser.add_argument("--source-data", default=None, help="Override manifest source_data")
    parser.add_argument("--write", action="store_true", help="Write MANIFEST.json")
    parser.add_argument("--verify", action="store_true", help="Exit non-zero if generated manifest differs")
    args = parser.parse_args()

    manifest_path = args.manifest or args.fixture_dir / DEFAULT_MANIFEST_NAME
    existing = load_manifest(manifest_path) if manifest_path.exists() else {}
    created = args.created or existing.get("created")
    source_commit = args.source_commit or existing.get("source_commit")

    if not created or not source_commit:
        print("ERROR: --created and --source-commit are required when no manifest exists", file=sys.stderr)
        return 2

    generated = build_manifest(
        args.fixture_dir,
        args.pivots,
        created=created,
        source_commit=source_commit,
        weights_path=args.weights,
        source_data=args.source_data
        or existing.get("source_data", "data/silver/{macro_daily,percentile_daily,temperature_daily}.parquet"),
    )

    if args.write:
        manifest_path.write_text(dump_manifest(generated))
        print(f"[manifest] written -> {manifest_path}")
        return 0

    if args.verify:
        if existing != generated:
            print(f"ERROR: {manifest_path} is stale. Run with --write to regenerate.", file=sys.stderr)
            return 1
        print(f"[manifest] verified -> {manifest_path}")
        return 0

    print(dump_manifest(generated), end="")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
