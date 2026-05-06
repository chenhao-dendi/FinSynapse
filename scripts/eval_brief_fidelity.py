#!/usr/bin/env python3
"""Brief fact-fidelity evaluation.

Checks that the deterministic template and (optionally) LLM-generated
briefs retain key numerical facts from the input FactPack. Does NOT
run in CI — intended for local pre-commit or ad-hoc use.

Metrics:
  - fact_retention_rate: % of key numbers that appear in the narrative
  - hallucination_rate: % of numbers in brief NOT found in input facts

Usage:
    uv run python scripts/eval_brief_fidelity.py
    uv run python scripts/eval_brief_fidelity.py --llm deepseek
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from finsynapse.report.facts import FactPack, _zone
from finsynapse.report.markdown import _template_narrative

FIXTURE_DIR = Path("tests/fixtures/eval_silver_2026Q1")


def _extract_numbers(text: str) -> list[float]:
    """Extract numbers followed by degree or percent markers from narrative text."""
    nums: list[float] = []
    for m in re.finditer(r"(\d+\.?\d*)\s*[°%℃]", text):
        nums.append(float(m.group(1)))
    return nums


def _build_facts_from_fixture() -> FactPack:
    temp = pd.read_parquet(FIXTURE_DIR / "temperature_daily.parquet")
    temp["date"] = pd.to_datetime(temp["date"])

    from finsynapse.dashboard.data import DashboardData

    empty_macro = pd.DataFrame(columns=["date", "indicator", "value", "source"])
    empty_pct = pd.DataFrame(columns=["date", "indicator", "value", "pct_5y", "pct_10y"])
    empty_div = pd.DataFrame(columns=["date", "pair_name", "strength", "is_divergent", "description"])
    empty_health = pd.DataFrame(columns=["date", "indicator", "check", "status"])

    data = DashboardData(
        temperature=temp,
        macro=empty_macro,
        percentile=empty_pct,
        divergence=empty_div,
        health=empty_health,
        silver_dir=FIXTURE_DIR,
    )

    latest = data.latest_per_market()
    asof = max(pd.to_datetime(row["date"]) for row in latest.values()).date().isoformat()

    facts = FactPack(asof=asof)
    for mkt in ("cn", "hk", "us"):
        if mkt not in latest:
            continue
        row = latest[mkt]
        facts.markets[mkt] = {
            "date": pd.to_datetime(row["date"]).date().isoformat(),
            "overall": float(row["overall"]) if not pd.isna(row.get("overall")) else None,
            "overall_zone": _zone(row.get("overall")),
            "valuation": None if pd.isna(row.get("valuation")) else float(row["valuation"]),
            "sentiment": None if pd.isna(row.get("sentiment")) else float(row["sentiment"]),
            "liquidity": None if pd.isna(row.get("liquidity")) else float(row["liquidity"]),
            "overall_change_1w": (
                None if pd.isna(row.get("overall_change_1w")) else float(row["overall_change_1w"])
            ),
            "valuation_contribution_1w": (
                None if pd.isna(row.get("valuation_contribution_1w"))
                else float(row["valuation_contribution_1w"])
            ),
            "sentiment_contribution_1w": (
                None if pd.isna(row.get("sentiment_contribution_1w"))
                else float(row["sentiment_contribution_1w"])
            ),
            "liquidity_contribution_1w": (
                None if pd.isna(row.get("liquidity_contribution_1w"))
                else float(row["liquidity_contribution_1w"])
            ),
            "data_quality": str(row.get("data_quality", "ok")),
        }
    return facts


def _collect_ground_truth(facts: FactPack) -> list[float]:
    numbers: list[float] = []
    for _mkt, info in facts.markets.items():
        for field in ["overall", "valuation", "sentiment", "liquidity"]:
            v = info.get(field)
            if v is not None and not pd.isna(v):
                numbers.append(round(float(v), 1))
    return numbers


def _fidelity_check(text: str, ground_truth: list[float]) -> dict:
    brief_numbers = _extract_numbers(text)
    gt_set = {round(g, 0) for g in ground_truth}

    matched_gt: set[float] = set()
    for n in brief_numbers:
        nr = round(n, 0)
        for gt_r in gt_set:
            if abs(nr - gt_r) < 0.5:
                matched_gt.add(gt_r)
                break

    hallucinated = sum(1 for n in brief_numbers if round(n, 0) not in gt_set)

    return {
        "ground_truth_count": len(ground_truth),
        "brief_number_count": len(brief_numbers),
        "unique_facts_found": len(matched_gt),
        "fact_retention_rate": round(len(matched_gt) / len(ground_truth), 3) if ground_truth else 0,
        "hallucinated_count": hallucinated,
        "hallucination_rate": round(hallucinated / max(len(brief_numbers), 1), 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Brief fact-fidelity evaluation")
    parser.add_argument("--llm", type=str, default=None, help="LLM provider to test (e.g. deepseek)")
    parser.add_argument("--model", type=str, default=None, help="LLM model override")
    args = parser.parse_args()

    print("=" * 72)
    print("  Brief Fact-Fidelity Evaluation")
    print("=" * 72)
    print()

    facts = _build_facts_from_fixture()
    ground_truth = _collect_ground_truth(facts)
    print(f"Ground truth numbers: {len(ground_truth)}")

    # Template
    template_narrative = _template_narrative(facts)
    template_result = _fidelity_check(template_narrative, ground_truth)
    print()
    print("Template (deterministic):")
    print(f"  fact retention: {template_result['fact_retention_rate']:.1%} "
          f"({template_result['unique_facts_found']}/{template_result['ground_truth_count']} unique)")
    print(f"  hallucinated:   {template_result['hallucinated_count']} / {template_result['brief_number_count']}")

    # LLM (if requested)
    if args.llm:
        print()
        print(f"Generating LLM brief via {args.llm}...")
        try:
            from finsynapse.report.llm import build_prompt, call_llm

            prompt = build_prompt(facts)
            llm_result = call_llm(prompt, provider=args.llm, model=args.model)
            if llm_result.text:
                llm_eval = _fidelity_check(llm_result.text, ground_truth)
                print(f"LLM ({args.llm}):")
                print(f"  fact retention: {llm_eval['fact_retention_rate']:.1%} "
                      f"({llm_eval['unique_facts_found']}/{llm_eval['ground_truth_count']} unique)")
                print(f"  hallucinated:   {llm_eval['hallucinated_count']} / {llm_eval['brief_number_count']}")
            else:
                print("  LLM returned empty response — check API key / network")
        except Exception as e:
            print(f"  LLM call failed: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
