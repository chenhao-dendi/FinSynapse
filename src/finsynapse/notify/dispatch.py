"""Push notifications via Bark (iOS) and Telegram. Both via webhook — no
SDK dependency, just `requests`. Either / both / neither can be configured;
absent secrets degrade silently with a log line."""
from __future__ import annotations

from dataclasses import dataclass

import requests

from finsynapse import config as _cfg
from finsynapse.notify.state import Event

BARK_URL = "https://api.day.app/{key}"
TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"
TIMEOUT = 10


@dataclass
class DispatchResult:
    bark_status: int | None = None
    telegram_status: int | None = None
    bark_skipped_reason: str | None = None
    telegram_skipped_reason: str | None = None


def _format_summary(events: list[Event]) -> tuple[str, str]:
    title = "🌡️ FinSynapse"
    if not events:
        return title, "无显著状态变化"
    lines = [e.summary for e in events]
    body = "\n".join(lines)
    if len(body) > 800:
        body = body[:780] + "\n…(truncated)"
    return title, body


def send_bark(title: str, body: str) -> tuple[int | None, str | None]:
    key = _cfg.settings.bark_device_key
    if not key:
        return None, "BARK_DEVICE_KEY not set"
    try:
        r = requests.post(
            BARK_URL.format(key=key),
            json={"title": title, "body": body, "group": "FinSynapse"},
            timeout=TIMEOUT,
        )
        return r.status_code, None
    except requests.RequestException as e:
        return None, f"bark error: {type(e).__name__}: {e}"


def send_telegram(text: str) -> tuple[int | None, str | None]:
    token = _cfg.settings.telegram_bot_token
    chat_id = _cfg.settings.telegram_chat_id
    if not (token and chat_id):
        return None, "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set"
    try:
        r = requests.post(
            TELEGRAM_URL.format(token=token),
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown",
                  "disable_web_page_preview": True},
            timeout=TIMEOUT,
        )
        return r.status_code, None
    except requests.RequestException as e:
        return None, f"telegram error: {type(e).__name__}: {e}"


def dispatch(events: list[Event]) -> DispatchResult:
    title, body = _format_summary(events)
    result = DispatchResult()

    # Skip silent dispatch when there's literally nothing to say AND neither
    # channel is configured. But if a channel IS configured, we still want
    # daily silence-confirms ("everything quiet") to be optional via env later.
    # For now: only send when there are real events.
    if not events:
        result.bark_skipped_reason = "no events"
        result.telegram_skipped_reason = "no events"
        return result

    result.bark_status, result.bark_skipped_reason = send_bark(title, body)

    md_body = f"*{title}*\n```\n{body}\n```"
    result.telegram_status, result.telegram_skipped_reason = send_telegram(md_body)

    return result
