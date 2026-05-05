"""Prompt construction and LLM provider calls for daily macro briefs."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import requests

from finsynapse import config as _cfg
from finsynapse.report.facts import FactPack

_SYSTEM_PROMPT = """你是 FinSynapse 的宏观市场观察员，负责为投资者撰写**每日中文市场简评**。

要求：
1. 只引用我提供的事实数字，**严禁编造任何数字**。如果某个值缺失，直接说"暂缺"而非估算。
2. 风格：克制、专业、短句。每段 2-3 句。不使用感叹号、不使用"震撼""暴涨"等情绪词。
3. 围绕三件事展开：
   - 三市场温度结构（哪个最热、哪个最冷、本周方向）
   - 最值得注意的 1-2 个背离信号（解释为什么重要）
   - 1 句话风险提示（基于温度区间或极端百分位）
4. 输出**纯 markdown**，不要包含 markdown 代码块围栏（```）。不要写标题（标题由我加）。
5. 总长度 250-400 字。
"""


def build_prompt(facts: FactPack) -> str:
    return (
        _SYSTEM_PROMPT
        + "\n\n以下是事实数据：\n\n"
        + json.dumps(
            {
                "asof": facts.asof,
                "markets": facts.markets,
                "recent_divergences": facts.divergences,
                "notable_indicators_pct10y": facts.notable_indicators,
                "data_health": {"fail": facts.health_fail_count, "warn": facts.health_warn_count},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@dataclass
class LLMResult:
    text: str
    provider: str  # "ollama" | "deepseek" | "anthropic" | "template"
    model: str | None = None
    error: str | None = None


def _call_ollama(prompt: str, model: str = "qwen2.5:7b", timeout: int = 120) -> str:
    """Local Ollama. Default model is qwen2.5:7b — strong CN capability and small enough
    to run on a laptop. User can override via FINSYNAPSE_LLM_MODEL env."""
    base_url = _cfg.settings.ollama_base_url.rstrip("/")
    r = requests.post(
        f"{base_url}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json().get("response", "").strip()


def _call_deepseek(prompt: str, model: str = "deepseek-chat", timeout: int = 300) -> str:
    api_key = _cfg.settings.deepseek_api_key
    if not api_key:
        raise RuntimeError("no DEEPSEEK_API_KEY")
    r = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
            "stream": False,
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _call_anthropic(prompt: str, model: str = "claude-haiku-4-5-20251001", timeout: int = 60) -> str:
    """Anthropic Messages API. Supports both direct (ANTHROPIC_API_KEY → x-api-key)
    and gateway/proxy setups (ANTHROPIC_AUTH_TOKEN → Bearer + ANTHROPIC_BASE_URL)."""
    api_key = _cfg.settings.anthropic_api_key
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
    if not api_key and not auth_token:
        raise RuntimeError("no ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN")

    headers = {"anthropic-version": "2023-06-01", "Content-Type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    r = requests.post(
        f"{base_url}/v1/messages",
        headers=headers,
        json={
            "model": model,
            "max_tokens": 800,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=timeout,
    )
    r.raise_for_status()
    payload = r.json()
    return "".join(b.get("text", "") for b in payload.get("content", [])).strip()


def call_llm(prompt: str, provider: str = "auto", model: str | None = None) -> LLMResult:
    """Try providers in order; return first success. `provider="auto"` walks
    ollama -> deepseek -> anthropic. Explicit provider skips the fallback."""
    order = ["ollama", "deepseek", "anthropic"] if provider == "auto" else [provider]

    last_err = None
    for p in order:
        try:
            if p == "ollama":
                text = _call_ollama(prompt, model=model or os.getenv("FINSYNAPSE_LLM_MODEL", "qwen2.5:7b"))
            elif p == "deepseek":
                text = _call_deepseek(prompt, model=model or "deepseek-chat")
            elif p == "anthropic":
                text = _call_anthropic(prompt, model=model or "claude-haiku-4-5-20251001")
            else:
                raise RuntimeError(f"unknown provider {p!r}")
            if text:
                return LLMResult(text=text, provider=p, model=model)
        except Exception as exc:
            last_err = f"{p}: {type(exc).__name__}: {exc}"
            continue

    return LLMResult(text="", provider="template", error=last_err)
