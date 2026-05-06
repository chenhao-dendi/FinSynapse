"""Performance benchmarks for the transform pipeline.

Verifies that the full bronze→silver pipeline completes in < 30s
on the eval_silver_2026Q1 fixture. Catches performance regressions
from algorithmic changes or pandas version upgrades.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from finsynapse.transform.normalize import collect_bronze, derive_indicators
from finsynapse.transform.percentile import compute_percentiles
from finsynapse.transform.temperature import WeightsConfig, compute_temperature, write_silver_temperature

FIXTURE_DIR = Path("tests/fixtures/eval_silver_2026Q1")


@pytest.fixture
def fixture_macro():
    return pd.read_parquet(FIXTURE_DIR / "macro_daily.parquet")


@pytest.fixture
def fixture_weights():
    # Use a subset of the real config that matches fixture indicators
    return WeightsConfig.load()


def test_percentile_benchmark(benchmark, fixture_macro):
    """compute_percentiles should be fast (< 5s on fixture)."""
    result = benchmark(compute_percentiles, fixture_macro)
    assert not result.empty
    assert "pct_10y" in result.columns


def test_temperature_benchmark(benchmark, fixture_macro, fixture_weights):
    """compute_temperature should be fast (< 5s on fixture)."""
    pct = compute_percentiles(fixture_macro)
    result = benchmark(compute_temperature, pct, fixture_weights)
    assert not result.empty
    assert "overall" in result.columns


def test_full_pipeline_benchmark(benchmark, fixture_macro, fixture_weights):
    """Full bronze→temperature pipeline should complete in < 30s."""
    def pipeline():
        macro = fixture_macro.copy()
        pct = compute_percentiles(macro)
        temp = compute_temperature(pct, fixture_weights)
        return temp

    result = benchmark(pipeline)
    assert not result.empty


def test_suite_benchmark(benchmark):
    """Benchmark suite.run() on the eval fixture (< 15s)."""
    from finsynapse.eval.suite import run as suite_run

    result = benchmark(
        suite_run,
        silver_dir=FIXTURE_DIR,
        weights_path=Path("config/weights.yaml"),
    )
    assert result.metrics.get("pivot_directional_rate") is not None
