from __future__ import annotations

import json
from pathlib import Path

from scripts.build_eval_fixture_manifest import build_manifest

FIXTURE_DIR = Path("tests/fixtures/eval_silver_2026Q1")
MANIFEST_PATH = FIXTURE_DIR / "MANIFEST.json"
PIVOTS_PATH = Path("scripts/backtest_pivots.yaml")


def test_eval_fixture_manifest_matches_generated_manifest():
    manifest = json.loads(MANIFEST_PATH.read_text())
    generated = build_manifest(
        FIXTURE_DIR,
        PIVOTS_PATH,
        created=manifest["created"],
        source_commit=manifest["source_commit"],
        source_data=manifest["source_data"],
    )
    assert generated == manifest


def test_eval_fixture_manifest_audits_indicator_pivot_coverage():
    manifest = json.loads(MANIFEST_PATH.read_text())
    coverage = manifest["indicator_pivot_coverage"]

    assert coverage["total_checks"] == 218
    assert coverage["available_checks"] == 184
    assert coverage["missing_checks"] == 34
    assert coverage["by_market"] == {
        "us": {"available": 76, "total": 90},
        "cn": {"available": 72, "total": 80},
        "hk": {"available": 36, "total": 48},
    }
    missing = coverage["missing_required_percentiles"]
    assert len(missing) == 34
    assert any(row["indicator"] == "us_hy_oas" and row["reason"] == "no_percentile_row" for row in missing)
