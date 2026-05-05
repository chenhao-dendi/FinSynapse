"""Markdown rendering and stored brief helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from finsynapse import config as _cfg
from finsynapse.dashboard.data import MARKETS
from finsynapse.dashboard.i18n import translate_div
from finsynapse.report.facts import FactPack, _zone, _zone_emoji
from finsynapse.report.llm import LLMResult


def _template_narrative(facts: FactPack) -> str:
    """Rule-based narrative when no LLM is reachable. Picks the hottest/coldest
    market, the strongest divergence, and a percentile-extreme note. Boring
    but never wrong."""
    parts: list[str] = []

    if facts.markets:
        rated = [(m, info["overall"]) for m, info in facts.markets.items() if info["overall"] is not None]
        if rated:
            rated.sort(key=lambda x: x[1], reverse=True)
            hottest_m, hottest_v = rated[0]
            coldest_m, coldest_v = rated[-1]
            parts.append(
                f"今日三市场温度：{hottest_m.upper()} 最热（{hottest_v:.0f}°，{_zone_emoji(_zone(hottest_v))}），"
                f"{coldest_m.upper()} 最冷（{coldest_v:.0f}°，{_zone_emoji(_zone(coldest_v))}）。"
            )

        for m in MARKETS:
            info = facts.markets.get(m, {})
            chg = info.get("overall_change_1w")
            if chg is not None and abs(chg) >= 5:
                direction = "升" if chg > 0 else "降"
                parts.append(f"{m.upper()} 一周综合温度{direction} {abs(chg):.1f}°。")

    if facts.divergences:
        top = facts.divergences[0]
        zh = translate_div(top["description"], "zh")
        parts.append(f"最近背离：**{top['pair']}**（{top['date']}）— {zh}。")

    if facts.notable_indicators:
        for n in facts.notable_indicators[:2]:
            tag = "极热" if n["pct_10y"] >= 85 else "极冷"
            parts.append(f"`{n['indicator']}` 当前 {n['value']:.2f}，处于 10 年 {n['pct_10y']:.0f}% 分位（{tag}）。")

    if not parts:
        parts.append("今日 silver 数据齐全，但未触发显著的温度/背离/百分位异常。")

    return "\n\n".join(parts)


def _fmt(v: float | None, suffix: str = "°", digits: int = 1) -> str:
    if v is None:
        return "—"
    return f"{v:.{digits}f}{suffix}"


def _fmt_signed(v: float | None, suffix: str = "°") -> str:
    if v is None:
        return "—"
    return f"{v:+.1f}{suffix}"


def render_markdown(facts: FactPack, narrative: str, llm: LLMResult) -> str:
    lines: list[str] = []
    lines.append(f"# FinSynapse 宏观简评 · {facts.asof}")
    lines.append("")
    lines.append(
        f"> 数据截至 **{facts.asof}** · "
        f"叙事生成: `{llm.provider}`" + (f" / `{llm.model}`" if llm.model else "") + " · "
        "数字直接来自 silver 层"
    )
    lines.append("")

    # --- 三市场温度快照（fact, deterministic）
    lines.append("## 一、三市场温度快照")
    lines.append("")
    lines.append("| 市场 | 使用日期 | 综合 | 区间 | 估值 | 情绪 | 流动性 | 一周Δ | 数据 |")
    lines.append("|------|:--------:|-----:|:----:|-----:|-----:|-------:|------:|------|")
    for m in MARKETS:
        info = facts.markets.get(m)
        if not info:
            lines.append(f"| {m.upper()} | — | — | — | — | — | — | — | _missing_ |")
            continue
        zone_label = f"{_zone_emoji(info['overall_zone'])} {info['overall_zone']}"
        lines.append(
            f"| {m.upper()} "
            f"| {info['date']} "
            f"| {_fmt(info['overall'])} "
            f"| {zone_label} "
            f"| {_fmt(info['valuation'])} "
            f"| {_fmt(info['sentiment'])} "
            f"| {_fmt(info['liquidity'])} "
            f"| {_fmt_signed(info['overall_change_1w'])} "
            f"| {info['data_quality']} |"
        )
    lines.append("")

    # --- 一周贡献度
    lines.append("### 一周温度变化贡献分解")
    lines.append("")
    lines.append("| 市场 | Δ估值 | Δ情绪 | Δ流动性 |")
    lines.append("|------|------:|------:|--------:|")
    for m in MARKETS:
        info = facts.markets.get(m)
        if not info:
            continue
        lines.append(
            f"| {m.upper()} "
            f"| {_fmt_signed(info['valuation_contribution_1w'])} "
            f"| {_fmt_signed(info['sentiment_contribution_1w'])} "
            f"| {_fmt_signed(info['liquidity_contribution_1w'])} |"
        )
    lines.append("")

    # --- 叙事
    lines.append("## 二、今日观察")
    lines.append("")
    lines.append(narrative.strip())
    lines.append("")

    # --- 背离明细 (fact)
    lines.append("## 三、最近背离信号")
    lines.append("")
    if facts.divergences:
        lines.append("| 日期 | 信号对 | a Δ% | b Δ% | 强度 | 含义 |")
        lines.append("|------|--------|-----:|-----:|-----:|------|")
        for d in facts.divergences:
            zh = translate_div(d["description"], "zh")
            lines.append(
                f"| {d['date']} | `{d['pair']}` "
                f"| {d['a_change_pct']:+.2f}% "
                f"| {d['b_change_pct']:+.2f}% "
                f"| {d['strength']:.4f} "
                f"| {zh} |"
            )
    else:
        lines.append("_近 5 个交易日无显著背离。_")
    lines.append("")

    # --- 极端百分位指标
    if facts.notable_indicators:
        lines.append("## 四、10 年百分位极值指标")
        lines.append("")
        lines.append("| 指标 | 当前值 | 10Y 百分位 | 标签 |")
        lines.append("|------|-------:|----------:|:----:|")
        for n in facts.notable_indicators:
            tag = "🔥 极热" if n["pct_10y"] >= 85 else "🧊 极冷"
            lines.append(f"| `{n['indicator']}` | {n['value']:.4g} | {n['pct_10y']:.1f}% | {tag} |")
        lines.append("")

    # --- 数据健康
    if facts.health_fail_count or facts.health_warn_count:
        lines.append("## 五、数据健康")
        lines.append("")
        lines.append(f"- fail: **{facts.health_fail_count}** 条；warn: **{facts.health_warn_count}** 条")
        lines.append("- 详见 `data/silver/health_log.parquet`")
        lines.append("")

    if llm.error:
        lines.append("---")
        lines.append(f"<sub>LLM fallback: {llm.error}</sub>")

    return "\n".join(lines).rstrip() + "\n"


_NARRATIVE_HEADER = "## 二、今日观察"
_NEXT_SECTION_PREFIX = "## "


def extract_narrative(md_text: str) -> str:
    """Slice out just the '今日观察' body — the only LLM-written part.

    The dashboard already renders temperature, divergence and percentile facts
    as charts/tables, so re-embedding the brief in full would be redundant.
    Returns the trimmed body (excluding the section heading itself); empty
    string when the section is absent (e.g. older brief format)."""
    lines = md_text.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() == _NARRATIVE_HEADER)
    except StopIteration:
        return ""
    body: list[str] = []
    for ln in lines[start + 1 :]:
        if ln.startswith(_NEXT_SECTION_PREFIX):
            break
        body.append(ln)
    return "\n".join(body).strip()


def latest_brief_path() -> Path | None:
    brief_dir = _cfg.settings.gold_dir / "brief"
    if not brief_dir.exists():
        return None
    candidates = sorted(brief_dir.glob("*.md"))
    return candidates[-1] if candidates else None


def load_latest_narrative() -> tuple[str, str | None]:
    """Return (narrative_md, asof_date_str) of the most recent brief, or
    ('', None) when no brief has been generated yet."""
    p = latest_brief_path()
    if p is None:
        return "", None
    text = p.read_text(encoding="utf-8")
    return extract_narrative(text), p.stem  # filename stem = YYYY-MM-DD


# Pattern matches the meta line written by render_markdown(), e.g.:
#   > 数据截至 **2026-04-29** · 叙事生成: `deepseek` / `deepseek-v4-pro` · ...
# Both `provider` and `/ model` are captured; model is optional (template
# fallback writes only the provider).
_META_PATTERN = re.compile(r"叙事生成:\s*`(?P<provider>[^`]+)`(?:\s*/\s*`(?P<model>[^`]+)`)?")


@dataclass(frozen=True)
class BriefMeta:
    """Lightweight summary of a stored brief — used by the archive page."""

    asof: str  # YYYY-MM-DD (filename stem)
    path: Path  # absolute path to .md
    provider: str  # "deepseek" | "anthropic" | "ollama" | "template" | "unknown"
    model: str | None  # model id, or None for template/older briefs


def _parse_meta(md_text: str) -> tuple[str, str | None]:
    """Pull (provider, model) out of the meta blockquote. Returns
    ('unknown', None) when the file pre-dates the meta line format."""
    for line in md_text.splitlines()[:10]:  # meta sits in the top few lines
        m = _META_PATTERN.search(line)
        if m:
            return m.group("provider"), m.group("model")
    return "unknown", None


def list_briefs() -> list[BriefMeta]:
    """Return every brief on disk, newest first. Used by render_static to
    build the /briefs.html archive index and per-date HTML pages."""
    brief_dir = _cfg.settings.gold_dir / "brief"
    if not brief_dir.exists():
        return []
    out: list[BriefMeta] = []
    for p in sorted(brief_dir.glob("*.md"), reverse=True):
        provider, model = _parse_meta(p.read_text(encoding="utf-8"))
        out.append(BriefMeta(asof=p.stem, path=p, provider=provider, model=model))
    return out


def write_brief(md: str, asof: str | date) -> Path:
    asof_str = asof.isoformat() if isinstance(asof, date) else asof
    out_dir = _cfg.settings.gold_dir / "brief"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{asof_str}.md"
    path.write_text(md, encoding="utf-8")
    return path
