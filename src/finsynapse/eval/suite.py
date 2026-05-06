"""BenchmarkSuite: pure-function evaluation of temperature against silver fixture.

Usage:
    uv run python -m finsynapse.eval.suite \\
        --silver tests/fixtures/eval_silver_2026Q1 \\
        --weights config/weights.yaml \\
        --out /tmp/latest.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from finsynapse.eval.metrics import (
    _build_metrics_dict,
    compute_bootstrap_ci,
    compute_config_hash,
    compute_forward_rho,
    compute_pivot_rates,
    compute_regime_stratified_ic,
    compute_rolling_ic,
)


@dataclass(frozen=True)
class SuiteResult:
    algo_version: str
    config_hash: str
    fixture_id: str
    metrics: dict
    per_market: dict
    pivot_details: list
    generated_at: str


DEFAULT_PIVOTS_PATH = Path("scripts/backtest_pivots.yaml")


def run(
    silver_dir: Path,
    weights_path: Path,
    pivots_path: Path = DEFAULT_PIVOTS_PATH,
    fixture_id: str | None = None,
) -> SuiteResult:
    """Pure: read silver parquet + weights, return SuiteResult. No file writes."""
    from finsynapse.transform.version import ALGO_VERSION

    macro = pd.read_parquet(silver_dir / "macro_daily.parquet")
    temp = pd.read_parquet(silver_dir / "temperature_daily.parquet")

    config_hash = compute_config_hash(weights_path)
    if fixture_id is None:
        fixture_id = _resolve_fixture_id(silver_dir)

    pivot_dir_rate, pivot_strict_rate, per_market_pivots, pivot_details = compute_pivot_rates(temp, pivots_path)
    forward_rho = compute_forward_rho(macro, temp)
    rolling_ic = compute_rolling_ic(macro, temp)
    regime_ic = compute_regime_stratified_ic(macro, temp)
    bootstrap = compute_bootstrap_ci(macro, temp)
    metrics, per_market = _build_metrics_dict(
        pivot_dir_rate, pivot_strict_rate, per_market_pivots, forward_rho, rolling_ic, regime_ic, bootstrap
    )

    return SuiteResult(
        algo_version=ALGO_VERSION,
        config_hash=config_hash,
        fixture_id=fixture_id,
        metrics=metrics,
        per_market=per_market,
        pivot_details=[_pivot_row_to_dict(r) for r in pivot_details],
        generated_at=datetime.now(UTC).isoformat(),
    )


def write_latest(result: SuiteResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_suite_result_to_dict(result), indent=2, ensure_ascii=False))


def _pivot_row_to_dict(row) -> dict:
    return {
        "label": row.label,
        "market": row.market,
        "date": row.pivot_date.isoformat(),
        "expected_zone": row.expected_zone,
        "temperature": round(row.temperature, 1),
        "zone": row.zone,
        "directional_pass": row.directional_pass,
        "strict_pass": row.strict_pass,
    }


def _suite_result_to_dict(result: SuiteResult) -> dict:
    return {
        "algo_version": result.algo_version,
        "config_hash": result.config_hash,
        "fixture_id": result.fixture_id,
        "metrics": result.metrics,
        "per_market": result.per_market,
        "pivot_details": result.pivot_details,
        "generated_at": result.generated_at,
    }


def _resolve_fixture_id(silver_dir: Path) -> str:
    import subprocess

    fixture_name = silver_dir.name
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=silver_dir.parent,
            text=True,
        ).strip()
    except Exception:
        sha = "unknown"
    return f"{fixture_name}@{sha}"


def _main() -> int:
    parser = argparse.ArgumentParser(description="Run benchmark suite against silver fixture")
    parser.add_argument("--silver", type=Path, required=True, help="Path to silver fixture directory")
    parser.add_argument("--weights", type=Path, required=True, help="Path to weights.yaml")
    parser.add_argument("--pivots", type=Path, default=DEFAULT_PIVOTS_PATH)
    parser.add_argument("--out", type=Path, required=True, help="Output JSON path")
    args = parser.parse_args()

    result = run(args.silver, args.weights, args.pivots)
    write_latest(result, args.out)
    print(json.dumps(result.metrics, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
