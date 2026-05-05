"""Daily macro brief generator (Phase 3).

Pipeline:
    silver layer  ->  fact pack (deterministic numbers)
                  ->  LLM narrative (or template fallback when no LLM available)
                  ->  data/gold/brief/YYYY-MM-DD.md

This module keeps the public orchestration entrypoint stable. The implementation
is split across `facts.py`, `llm.py`, and `markdown.py` so each layer can evolve
without turning brief generation into one large mixed-responsibility file.
"""

from __future__ import annotations

from pathlib import Path

from finsynapse.report.facts import FactPack, _zone, _zone_emoji, assemble_facts
from finsynapse.report.llm import LLMResult, build_prompt, call_llm
from finsynapse.report.markdown import (
    BriefMeta,
    _template_narrative,
    extract_narrative,
    latest_brief_path,
    list_briefs,
    load_latest_narrative,
    render_markdown,
    write_brief,
)

__all__ = [
    "BriefMeta",
    "FactPack",
    "LLMResult",
    "_template_narrative",
    "_zone",
    "_zone_emoji",
    "assemble_facts",
    "build_prompt",
    "call_llm",
    "extract_narrative",
    "generate",
    "latest_brief_path",
    "list_briefs",
    "load_latest_narrative",
    "render_markdown",
    "write_brief",
]


def generate(provider: str = "auto", model: str | None = None) -> tuple[Path, LLMResult]:
    """End-to-end: facts -> prompt -> LLM -> markdown -> file. Returns (path, llm_result)."""
    facts = assemble_facts()
    prompt = build_prompt(facts)
    llm = call_llm(prompt, provider=provider, model=model)
    narrative = llm.text if llm.text else _template_narrative(facts)
    md = render_markdown(facts, narrative, llm)
    path = write_brief(md, facts.asof)
    return path, llm
