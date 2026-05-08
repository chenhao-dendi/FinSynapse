"""Validate config/data_sources.yaml against code-level providers and weights."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from finsynapse.transform.health_check import PLAUSIBLE_BOUNDS

CATALOG_PATH = Path("config/data_sources.yaml")
WEIGHTS_PATH = Path("config/weights.yaml")
FIXTURE_MACRO_PATH = Path("tests/fixtures/eval_silver_2026Q1/macro_daily.parquet")
BOUND_REQUIRED_USAGES = {"weighted", "collected_only"}
KNOWN_GAP_STATUSES = {"unresolved", "source_candidate", "source_ready", "requires_fixture_rebuild"}


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())


def catalog_indicators(catalog: dict[str, Any]) -> set[str]:
    indicators: set[str] = set()
    for source in catalog.get("sources", {}).values():
        indicators.update(source.get("indicators", {}).keys())
    return indicators


def weighted_indicators(weights_path: Path = WEIGHTS_PATH) -> set[str]:
    weights = yaml.safe_load(weights_path.read_text())
    indicators: set[str] = set()
    for block in weights.get("indicator_weights", {}).values():
        indicators.update(block.keys())
    return indicators


def fixture_indicators(fixture_macro_path: Path = FIXTURE_MACRO_PATH) -> set[str]:
    if not fixture_macro_path.exists():
        return set()
    import pandas as pd

    df = pd.read_parquet(fixture_macro_path, columns=["indicator"])
    return set(df["indicator"].astype(str).unique())


def validate_catalog(
    catalog_path: Path = CATALOG_PATH,
    weights_path: Path = WEIGHTS_PATH,
    fixture_macro_path: Path = FIXTURE_MACRO_PATH,
) -> list[str]:
    catalog = load_catalog(catalog_path)
    errors: list[str] = []

    sources = catalog.get("sources", {})
    if not isinstance(sources, dict) or not sources:
        return ["catalog has no sources"]

    from finsynapse.cli import SOURCES

    missing_sources = sorted(set(SOURCES) - set(sources))
    if missing_sources:
        errors.append(f"missing provider source entries: {missing_sources}")

    known_indicators = catalog_indicators(catalog)
    missing_weighted = sorted(weighted_indicators(weights_path) - known_indicators)
    if missing_weighted:
        errors.append(f"weighted indicators missing from catalog: {missing_weighted}")

    missing_fixture = sorted(fixture_indicators(fixture_macro_path) - known_indicators)
    if missing_fixture:
        errors.append(f"fixture macro indicators missing from catalog: {missing_fixture}")

    for source_name, source in sorted(sources.items()):
        indicators = source.get("indicators", {})
        if not indicators:
            errors.append(f"{source_name}: no indicators listed")
        if source.get("tier") not in {"official_public", "public_vendor", "derived"}:
            errors.append(f"{source_name}: invalid tier {source.get('tier')!r}")
        if source.get("status") not in {"active", "fallback", "collected_only"}:
            errors.append(f"{source_name}: invalid status {source.get('status')!r}")
        if source.get("tier") == "official_public" and source.get("access") not in {"keyless_free", "free_api_key"}:
            errors.append(f"{source_name}: official_public source must use free public access")

        provider = source.get("provider")
        if provider and not Path(provider).exists():
            errors.append(f"{source_name}: provider path does not exist: {provider}")

        for indicator, meta in sorted(indicators.items()):
            usage = meta.get("usage") if isinstance(meta, dict) else None
            if usage not in {"weighted", "collected_only", "forward_return_index", "context"}:
                errors.append(f"{source_name}.{indicator}: invalid usage {usage!r}")
            if usage in BOUND_REQUIRED_USAGES and indicator not in PLAUSIBLE_BOUNDS:
                errors.append(f"{source_name}.{indicator}: {usage} indicator missing health_check.PLAUSIBLE_BOUNDS")

    gaps = catalog.get("known_gaps", {})
    if not isinstance(gaps, dict) or not gaps:
        errors.append("catalog should explicitly track known_gaps")
    else:
        for gap_name, gap in sorted(gaps.items()):
            status = gap.get("status") if isinstance(gap, dict) else None
            if status not in KNOWN_GAP_STATUSES:
                errors.append(f"known_gaps.{gap_name}: invalid status {status!r}")

    return errors


def _main() -> int:
    parser = argparse.ArgumentParser(description="Validate data source catalog coverage")
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--weights", type=Path, default=WEIGHTS_PATH)
    parser.add_argument("--fixture-macro", type=Path, default=FIXTURE_MACRO_PATH)
    args = parser.parse_args()

    errors = validate_catalog(args.catalog, args.weights, args.fixture_macro)
    if errors:
        print("Data source catalog check FAILED:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(f"[catalog] verified -> {args.catalog}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
