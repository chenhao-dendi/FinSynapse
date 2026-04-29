"""Tests for report.brief — the daily macro brief generator.

We don't hit any LLM; we exercise the deterministic pipeline (assemble facts
from a fake silver dir, render markdown via the template fallback) so the
test runs offline and finishes in milliseconds.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from finsynapse.report.brief import (
    FactPack,
    LLMResult,
    _template_narrative,
    assemble_facts,
    extract_narrative,
    load_latest_narrative,
    render_markdown,
    write_brief,
)


def _seed_silver(tmp_dir):
    """Plant a minimal but realistic silver layer under tmp_dir."""
    silver = tmp_dir / "silver"
    silver.mkdir(parents=True, exist_ok=True)

    today = pd.Timestamp("2026-04-28")
    temp = pd.DataFrame(
        [
            {
                "date": today.date(),
                "market": m,
                "overall": o,
                "valuation": v,
                "sentiment": s,
                "liquidity": liq,
                "data_quality": "ok",
                "valuation_contribution_1w": 1.0,
                "sentiment_contribution_1w": -0.5,
                "liquidity_contribution_1w": 0.2,
                "overall_change_1w": 0.7,
            }
            for m, o, v, s, liq in [
                ("cn", 75.0, 70.0, 90.0, 60.0),
                ("hk", 32.0, 8.0, 90.0, 30.0),
                ("us", 60.0, 96.0, 43.0, 30.0),
            ]
        ]
    )
    temp.to_parquet(silver / "temperature_daily.parquet", index=False)

    div = pd.DataFrame(
        [
            {
                "date": today.date(),
                "pair_name": "csi300_volume",
                "a_change": 0.005,
                "b_change": -0.01,
                "is_divergent": True,
                "strength": 0.0050,
                "description": "CSI300 ↑ + turnover ↓: rally without participation — distribution risk",
            },
            {
                "date": today.date(),
                "pair_name": "sp500_vix",
                "a_change": 0.003,
                "b_change": 0.012,
                "is_divergent": True,
                "strength": 0.0036,
                "description": "SP500 ↑ + VIX ↑: rising on rising fear — beware",
            },
        ]
    )
    div.to_parquet(silver / "divergence_daily.parquet", index=False)

    pct = pd.DataFrame(
        [
            {
                "date": today.date(),
                "indicator": "us_cape",
                "value": 40.5,
                "pct_1y": 99.0,
                "pct_5y": 99.5,
                "pct_10y": 100.0,
            },
            {"date": today.date(), "indicator": "vix", "value": 12.0, "pct_1y": 5.0, "pct_5y": 8.0, "pct_10y": 10.0},
        ]
    )
    pct.to_parquet(silver / "percentile_daily.parquet", index=False)

    macro = pd.DataFrame(columns=["date", "indicator", "value", "source"])
    macro.to_parquet(silver / "macro_daily.parquet", index=False)
    health = pd.DataFrame(columns=["date", "indicator", "rule", "severity", "detail"])
    health.to_parquet(silver / "health_log.parquet", index=False)


def test_assemble_facts_extracts_three_markets_and_extremes(tmp_data_dir):
    _seed_silver(tmp_data_dir)
    facts = assemble_facts()

    assert facts.asof == "2026-04-28"
    assert set(facts.markets) == {"cn", "hk", "us"}
    assert facts.markets["cn"]["overall_zone"] == "hot"
    assert facts.markets["hk"]["overall_zone"] == "mid"

    pair_names = {d["pair"] for d in facts.divergences}
    assert "csi300_volume" in pair_names

    notable = {n["indicator"] for n in facts.notable_indicators}
    assert "us_cape" in notable  # 100th pct → extreme
    assert "vix" in notable  # 10th pct → extreme


def test_template_narrative_mentions_hottest_and_coldest_market(tmp_data_dir):
    _seed_silver(tmp_data_dir)
    facts = assemble_facts()
    narrative = _template_narrative(facts)
    assert "CN" in narrative and "HK" in narrative
    assert "csi300_volume" in narrative or "sp500_vix" in narrative


def test_render_markdown_includes_all_sections_and_facts(tmp_data_dir):
    _seed_silver(tmp_data_dir)
    facts = assemble_facts()
    narrative = _template_narrative(facts)
    md = render_markdown(facts, narrative, LLMResult(text="", provider="template"))

    # Headers from each section
    assert "# FinSynapse 宏观简评" in md
    assert "三市场温度快照" in md
    assert "今日观察" in md
    assert "最近背离信号" in md
    assert "10 年百分位极值指标" in md

    # Numbers must appear verbatim (LLM didn't render the tables — we did)
    assert "75.0°" in md or "75.0" in md
    assert "us_cape" in md
    assert "100.0%" in md


def test_extract_narrative_returns_only_observation_section():
    md = (
        "# title\n\n"
        "## 一、温度快照\n\nignore me\n\n"
        "## 二、今日观察\n\n"
        "first paragraph.\n\nsecond paragraph.\n\n"
        "## 三、最近背离信号\n\nignore me too\n"
    )
    body = extract_narrative(md)
    assert "first paragraph" in body
    assert "second paragraph" in body
    assert "ignore me" not in body
    assert "## " not in body  # heading is stripped


def test_extract_narrative_returns_empty_when_section_missing():
    assert extract_narrative("# just a title\n\nbody only\n") == ""


def test_load_latest_narrative_picks_lexically_last_md(tmp_data_dir):
    brief_dir = tmp_data_dir / "gold" / "brief"
    brief_dir.mkdir(parents=True)
    (brief_dir / "2026-04-27.md").write_text("# x\n\n## 二、今日观察\n\nold\n", encoding="utf-8")
    (brief_dir / "2026-04-29.md").write_text("# x\n\n## 二、今日观察\n\nnew\n", encoding="utf-8")

    body, asof = load_latest_narrative()
    assert asof == "2026-04-29"
    assert body == "new"


def test_write_brief_writes_idempotent_file(tmp_data_dir):
    _seed_silver(tmp_data_dir)
    facts = assemble_facts()
    md = render_markdown(facts, "test narrative", LLMResult(text="x", provider="template"))
    p1 = write_brief(md, facts.asof)
    p2 = write_brief(md, facts.asof)
    assert p1 == p2
    assert p1.exists()
    assert p1.parent.name == "brief"
    assert p1.read_text(encoding="utf-8").startswith("# FinSynapse 宏观简评")
