"""Compare two eval silver fixtures for PR review.

This is intentionally diagnostic: a candidate fixture may improve data
coverage while failing a champion gate because a newly-live indicator changes a
historical pivot classification. The report makes that tradeoff explicit
instead of silently replacing the baseline fixture.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from finsynapse.eval.champion import diff
from finsynapse.eval.suite import run as run_suite
from finsynapse.transform.temperature import SUB_NAMES, WeightsConfig
from scripts.build_eval_fixture_manifest import (
    DEFAULT_PIVOTS_PATH,
    DEFAULT_WEIGHTS_PATH,
    build_manifest,
)


@dataclass(frozen=True)
class FixtureComparison:
    baseline_dir: Path
    candidate_dir: Path
    baseline_manifest: dict[str, Any]
    candidate_manifest: dict[str, Any]
    baseline_suite: dict[str, Any]
    candidate_suite: dict[str, Any]
    gate_report: Any
    weights_path: Path


def build_comparison(
    baseline_dir: Path,
    candidate_dir: Path,
    weights_path: Path = DEFAULT_WEIGHTS_PATH,
    pivots_path: Path = DEFAULT_PIVOTS_PATH,
) -> FixtureComparison:
    baseline_manifest = build_manifest(
        baseline_dir,
        pivots_path,
        created="comparison",
        source_commit=baseline_dir.name,
        weights_path=weights_path,
    )
    candidate_manifest = build_manifest(
        candidate_dir,
        pivots_path,
        created="comparison",
        source_commit=candidate_dir.name,
        weights_path=weights_path,
    )
    baseline_suite = run_suite(baseline_dir, weights_path, pivots_path, fixture_id=baseline_dir.name)
    candidate_suite = run_suite(candidate_dir, weights_path, pivots_path, fixture_id=candidate_dir.name)
    baseline_dict = _suite_to_dict(baseline_suite)
    candidate_dict = _suite_to_dict(candidate_suite)
    return FixtureComparison(
        baseline_dir=baseline_dir,
        candidate_dir=candidate_dir,
        baseline_manifest=baseline_manifest,
        candidate_manifest=candidate_manifest,
        baseline_suite=baseline_dict,
        candidate_suite=candidate_dict,
        gate_report=diff(baseline_dict, candidate_dict),
        weights_path=weights_path,
    )


def render_markdown(comparison: FixtureComparison) -> str:
    base_manifest = comparison.baseline_manifest
    cand_manifest = comparison.candidate_manifest
    base_cov = base_manifest["indicator_pivot_coverage"]
    cand_cov = cand_manifest["indicator_pivot_coverage"]
    base_macro = base_manifest["files"]["macro_daily.parquet"]
    cand_macro = cand_manifest["files"]["macro_daily.parquet"]

    base_indicators = set(base_macro.get("indicators", []))
    cand_indicators = set(cand_macro.get("indicators", []))
    added = sorted(cand_indicators - base_indicators)
    removed = sorted(base_indicators - cand_indicators)

    lines = [
        "## Eval Fixture Candidate Comparison",
        "",
        "### Inputs",
        "",
        f"- Baseline: `{comparison.baseline_dir}`",
        f"- Candidate: `{comparison.candidate_dir}`",
        "",
        "### Coverage Delta",
        "",
        f"- Macro rows: {base_macro['rows']:,} -> {cand_macro['rows']:,} ({_signed(cand_macro['rows'] - base_macro['rows'])})",
        f"- Macro indicators: {len(base_indicators)} -> {len(cand_indicators)} ({_signed(len(cand_indicators) - len(base_indicators))})",
        f"- Added indicators: {_fmt_list(added)}",
        f"- Removed indicators: {_fmt_list(removed)}",
        "- Indicator pivot checks: "
        f"{base_cov['available_checks']}/{base_cov['total_checks']} -> "
        f"{cand_cov['available_checks']}/{cand_cov['total_checks']} "
        f"({_signed(cand_cov['available_checks'] - base_cov['available_checks'])})",
        f"- Missing required checks: {base_cov['missing_checks']} -> {cand_cov['missing_checks']} "
        f"({_signed(cand_cov['missing_checks'] - base_cov['missing_checks'])})",
        f"- By market: {_fmt_market_delta(base_cov['by_market'], cand_cov['by_market'])}",
        "",
        "### Gate Diff",
        "",
    ]

    for row in comparison.gate_report.rows:
        result = "PASS" if row.passed else "FAIL"
        lines.append(
            f"- `{row.metric}`: {_fmt_float(row.champion)} -> {_fmt_float(row.challenger)} "
            f"({_fmt_delta(row.delta)}, {row.severity}, {result})"
        )

    lines.extend(["", "### Required Percentile Coverage Delta", ""])
    lines.extend(_render_missing_required_delta(base_cov, cand_cov))

    changed_pivots = _changed_pivots(
        comparison.baseline_suite["pivot_details"], comparison.candidate_suite["pivot_details"]
    )
    lines.extend(["", "### Pivot Changes", ""])
    if not changed_pivots:
        lines.append("- none")
    else:
        for old, new in changed_pivots:
            markers = []
            if old["directional_pass"] != new["directional_pass"]:
                markers.append("direction")
            if old["strict_pass"] != new["strict_pass"]:
                markers.append("strict")
            if old["zone"] != new["zone"]:
                markers.append("zone")
            lines.append(
                f"- {new['market']} {new['date']} `{new['label']}` "
                f"[{', '.join(markers)}]: {old['temperature']} {old['zone']} -> "
                f"{new['temperature']} {new['zone']} (expected {new['expected_zone']})"
            )
            lines.extend(
                _render_pivot_decomposition(
                    comparison.baseline_dir,
                    comparison.candidate_dir,
                    comparison.weights_path,
                    new,
                )
            )

    return "\n".join(lines) + "\n"


def _suite_to_dict(result) -> dict[str, Any]:
    return {
        "metrics": result.metrics,
        "per_market": result.per_market,
        "pivot_details": result.pivot_details,
    }


def _changed_pivots(base_rows: list[dict[str, Any]], cand_rows: list[dict[str, Any]]) -> list[tuple[dict, dict]]:
    by_label = {row["label"]: row for row in base_rows}
    changed = []
    for new in cand_rows:
        old = by_label.get(new["label"])
        if not old:
            continue
        if (
            old["directional_pass"] != new["directional_pass"]
            or old["strict_pass"] != new["strict_pass"]
            or old["zone"] != new["zone"]
        ):
            changed.append((old, new))
    return changed


def _render_pivot_decomposition(
    baseline_dir: Path,
    candidate_dir: Path,
    weights_path: Path,
    pivot: dict[str, Any],
) -> list[str]:
    market = pivot["market"]
    target = pd.Timestamp(pivot["date"])
    cfg = WeightsConfig.load(weights_path)
    indicators = _market_indicator_specs(cfg, market)
    base_temp = _latest_temp_row(baseline_dir, market, target)
    cand_temp = _latest_temp_row(candidate_dir, market, target)
    base_pct = _latest_pct_by_indicator(baseline_dir, indicators, target)
    cand_pct = _latest_pct_by_indicator(candidate_dir, indicators, target)

    lines = [
        f"  - subtemps: {_fmt_subtemps(base_temp)} -> {_fmt_subtemps(cand_temp)}",
        "  - indicator percentiles:",
    ]
    for indicator, spec in indicators.items():
        window = spec.get("window", cfg.percentile_window)
        direction = spec["direction"]
        base = base_pct.get(indicator)
        cand = cand_pct.get(indicator)
        lines.append(
            f"    - `{indicator}` ({window}, dir {direction}): "
            f"{_fmt_pct_cell(base, window)} -> {_fmt_pct_cell(cand, window)}"
        )
    return lines


def _market_indicator_specs(cfg: WeightsConfig, market: str) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for sub in SUB_NAMES:
        for indicator, spec in cfg.indicator_weights.get(f"{market}_{sub}", {}).items():
            specs[indicator] = spec
    return dict(sorted(specs.items()))


def _latest_temp_row(fixture_dir: Path, market: str, target: pd.Timestamp) -> dict[str, Any] | None:
    temp = pd.read_parquet(fixture_dir / "temperature_daily.parquet")
    temp["date"] = pd.to_datetime(temp["date"])
    sub = temp[(temp["market"] == market) & (temp["date"] <= target)].sort_values("date").tail(1)
    if sub.empty:
        return None
    return sub.iloc[0].to_dict()


def _latest_pct_by_indicator(
    fixture_dir: Path,
    indicators: dict[str, dict[str, Any]],
    target: pd.Timestamp,
) -> dict[str, dict[str, Any]]:
    pct = pd.read_parquet(fixture_dir / "percentile_daily.parquet")
    pct["date"] = pd.to_datetime(pct["date"])
    out: dict[str, dict[str, Any]] = {}
    for indicator in indicators:
        sub = pct[(pct["indicator"] == indicator) & (pct["date"] <= target)].sort_values("date").tail(1)
        if not sub.empty:
            out[indicator] = sub.iloc[0].to_dict()
    return out


def _fmt_subtemps(row: dict[str, Any] | None) -> str:
    if row is None:
        return "no-row"
    parts = [f"overall={_fmt_num(row.get('overall'))}"]
    for sub in SUB_NAMES:
        parts.append(f"{sub}={_fmt_num(row.get(sub))}")
    return ", ".join(parts)


def _fmt_pct_cell(row: dict[str, Any] | None, window: str) -> str:
    if row is None:
        return "missing"
    return f"{_fmt_num(row.get(window))} on {pd.Timestamp(row['date']).date()}"


def _render_missing_required_delta(base_cov: dict[str, Any], cand_cov: dict[str, Any]) -> list[str]:
    base_missing = {_missing_required_key(row): row for row in base_cov["missing_required_percentiles"]}
    cand_missing = {_missing_required_key(row): row for row in cand_cov["missing_required_percentiles"]}

    resolved_keys = sorted(set(base_missing) - set(cand_missing))
    new_keys = sorted(set(cand_missing) - set(base_missing))

    lines = [
        f"- Resolved missing checks: {_fmt_missing_summary([base_missing[key] for key in resolved_keys])}",
        f"- Newly missing checks: {_fmt_missing_summary([cand_missing[key] for key in new_keys])}",
    ]
    if resolved_keys:
        lines.extend(["", "Resolved detail:"])
        lines.extend(_fmt_missing_details([base_missing[key] for key in resolved_keys]))
    if new_keys:
        lines.extend(["", "New missing detail:"])
        lines.extend(_fmt_missing_details([cand_missing[key] for key in new_keys]))
    return lines


def _missing_required_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (row["pivot_label"], row["market"], row["indicator"], row["required_window"])


def _fmt_missing_summary(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "none"
    counts: dict[str, int] = {}
    for row in rows:
        indicator = row["indicator"]
        counts[indicator] = counts.get(indicator, 0) + 1
    return ", ".join(f"`{indicator}`={count}" for indicator, count in sorted(counts.items()))


def _fmt_missing_details(rows: list[dict[str, Any]], *, limit: int = 20) -> list[str]:
    out = [
        f"- {row['market']} {row['pivot_date']} `{row['pivot_label']}`: "
        f"`{row['indicator']}` {row['required_window']} ({row['reason']})"
        for row in rows[:limit]
    ]
    remaining = len(rows) - limit
    if remaining > 0:
        out.append(f"- ... {remaining} more")
    return out


def _fmt_num(value: Any) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{float(value):.1f}"


def _fmt_market_delta(base: dict[str, dict[str, int]], cand: dict[str, dict[str, int]]) -> str:
    parts = []
    for market in sorted(set(base) | set(cand)):
        b = base.get(market, {})
        c = cand.get(market, {})
        b_avail = b.get("available", 0)
        c_avail = c.get("available", 0)
        total = c.get("total", b.get("total", 0))
        parts.append(f"{market}={b_avail}/{total}->{c_avail}/{total} ({_signed(c_avail - b_avail)})")
    return ", ".join(parts)


def _fmt_list(values: list[str]) -> str:
    return ", ".join(values) if values else "none"


def _signed(value: int) -> str:
    return f"{value:+d}"


def _fmt_float(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.4f}"


def _fmt_delta(value: float | None) -> str:
    return "N/A" if value is None else f"{value:+.4f}"


def _main() -> int:
    parser = argparse.ArgumentParser(description="Compare two eval silver fixtures")
    parser.add_argument("--baseline", type=Path, default=Path("tests/fixtures/eval_silver_2026Q1"))
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS_PATH)
    parser.add_argument("--pivots", type=Path, default=DEFAULT_PIVOTS_PATH)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    comparison = build_comparison(args.baseline, args.candidate, args.weights, args.pivots)
    report = render_markdown(comparison)
    if args.out:
        args.out.write_text(report)
        print(f"[fixture-compare] written -> {args.out}")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
