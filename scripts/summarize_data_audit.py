"""Render a Markdown data-audit summary for PR descriptions."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import yaml

CATALOG_PATH = Path("config/data_sources.yaml")
MANIFEST_PATH = Path("tests/fixtures/eval_silver_2026Q1/MANIFEST.json")


def build_summary(catalog_path: Path = CATALOG_PATH, manifest_path: Path = MANIFEST_PATH) -> str:
    catalog = yaml.safe_load(catalog_path.read_text())
    manifest = json.loads(manifest_path.read_text())

    sources = catalog["sources"]
    tier_counts = Counter(source["tier"] for source in sources.values())
    status_counts = Counter(source["status"] for source in sources.values())

    usage_to_indicators: dict[str, set[str]] = defaultdict(set)
    indicator_to_sources: dict[str, list[str]] = defaultdict(list)
    for source_name, source in sources.items():
        for indicator, meta in source.get("indicators", {}).items():
            usage_to_indicators[meta["usage"]].add(indicator)
            indicator_to_sources[indicator].append(source_name)

    official_sources = sorted(name for name, source in sources.items() if source["tier"] == "official_public")
    academic_sources = sorted(name for name, source in sources.items() if source["tier"] == "academic_public")
    collected_only = sorted(usage_to_indicators.get("collected_only", set()))
    weighted = sorted(usage_to_indicators.get("weighted", set()))
    known_gaps = catalog.get("known_gaps", {})

    macro_file = manifest["files"]["macro_daily.parquet"]
    pct_file = manifest["files"]["percentile_daily.parquet"]
    temp_file = manifest["files"]["temperature_daily.parquet"]
    pivot = manifest["pivot_coverage"]
    indicator_pivot = manifest.get("indicator_pivot_coverage", {})
    missing_indicator_counts = Counter(
        row["indicator"] for row in indicator_pivot.get("missing_required_percentiles", [])
    )

    lines = [
        "## Data Audit Summary",
        "",
        "### Source Catalog",
        "",
        f"- Source entries: {len(sources)}",
        f"- Official public sources: {len(official_sources)} ({', '.join(official_sources)})",
        f"- Academic public sources: {len(academic_sources)} ({', '.join(academic_sources)})",
        f"- Source tiers: {_fmt_counter(tier_counts)}",
        f"- Source statuses: {_fmt_counter(status_counts)}",
        f"- Weighted indicators cataloged: {len(weighted)}",
        f"- Collected-only research candidates: {len(collected_only)} ({', '.join(collected_only)})",
        "",
        "### Eval Fixture",
        "",
        f"- Fixture: `{manifest['fixture_id']}` from `{manifest['source_commit']}`",
        f"- Date window: {manifest['date_window']['start']} .. {manifest['date_window']['end']}",
        f"- Macro rows: {macro_file['rows']:,} across {len(macro_file.get('indicators', []))} indicators",
        f"- Percentile rows: {pct_file['rows']:,}",
        f"- Temperature rows: {temp_file['rows']:,} across {', '.join(temp_file.get('markets', []))}",
        f"- Pivot coverage: {pivot['covered']}/{pivot['total']} ({_fmt_counter(pivot['by_market'])})",
        "- Indicator pivot checks: "
        f"{indicator_pivot.get('available_checks', 0)}/{indicator_pivot.get('total_checks', 0)} "
        f"({_fmt_market_coverage(indicator_pivot.get('by_market', {}))})",
        f"- Missing required indicator-window checks: {indicator_pivot.get('missing_checks', 0)} "
        f"({_fmt_counter(missing_indicator_counts)})",
        f"- Top fixture data gaps: {_fmt_top_counter(missing_indicator_counts, n=5)}",
        "",
        "### Known Gaps",
        "",
    ]

    for gap_name, gap in sorted(known_gaps.items()):
        lines.append(f"- `{gap_name}` ({gap['market']}): {gap['status']} - {gap['notes']}")

    lines.extend(
        [
            "",
            "### Verification Commands",
            "",
            "- `uv run python scripts/check_data_source_catalog.py`",
            "- `uv run python scripts/build_eval_fixture_manifest.py --verify`",
            "- `uv run python -m finsynapse.eval.gate --champion eval/champion.json --challenger /tmp/finsynapse-latest.json`",
        ]
    )

    return "\n".join(lines) + "\n"


def _fmt_counter(counter: Counter | dict[str, int]) -> str:
    if not counter:
        return "none"
    return ", ".join(f"{k}={v}" for k, v in sorted(counter.items()))


def _fmt_top_counter(counter: Counter, n: int) -> str:
    if not counter:
        return "none"
    return ", ".join(f"{k}={v}" for k, v in counter.most_common(n))


def _fmt_market_coverage(by_market: dict[str, dict[str, int]]) -> str:
    if not by_market:
        return "none"
    return ", ".join(
        f"{market}={stats.get('available', 0)}/{stats.get('total', 0)}" for market, stats in sorted(by_market.items())
    )


def _main() -> int:
    parser = argparse.ArgumentParser(description="Render data-audit Markdown summary")
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    summary = build_summary(args.catalog, args.manifest)
    if args.out:
        args.out.write_text(summary)
        print(f"[data-audit] written -> {args.out}")
    else:
        print(summary, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
