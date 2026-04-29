from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from finsynapse.notify.dispatch import _format_summary, dispatch, send_bark, send_telegram
from finsynapse.notify.state import Event, _pick_meaningful_pair, zone


def test_zone_classifier_boundaries():
    assert zone(0) == "cold"
    assert zone(29.9) == "cold"
    assert zone(30.0) == "mid"
    assert zone(69.9) == "mid"
    assert zone(70.0) == "hot"
    assert zone(100.0) == "hot"
    assert zone(float("nan")) == "unknown"


def _temp_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_pick_meaningful_pair_skips_partial_phantom_rows():
    """Common production scenario: monthly indicator ffilled past last daily
    data, so the most-recent row has only valuation. Must not pair against it."""
    df = _temp_df(
        [
            {"date": "2026-04-25", "overall": 60, "valuation": 80, "sentiment": 50, "liquidity": 50},
            {"date": "2026-04-26", "overall": 65, "valuation": 80, "sentiment": 60, "liquidity": 55},
            # Phantom: only valuation present (sentiment+liquidity NaN due to ffill)
            {
                "date": "2026-04-29",
                "overall": 80,
                "valuation": 80,
                "sentiment": float("nan"),
                "liquidity": float("nan"),
            },
        ]
    )
    pair = _pick_meaningful_pair(df)
    assert pair is not None
    yesterday, today = pair
    # Should pair the two complete rows, NOT the phantom row.
    assert today["date"] == "2026-04-26"
    assert yesterday["date"] == "2026-04-25"


def test_pick_meaningful_pair_returns_none_with_one_row():
    df = _temp_df([{"date": "2026-04-25", "overall": 60, "valuation": 80, "sentiment": 50, "liquidity": 50}])
    assert _pick_meaningful_pair(df) is None


def test_format_summary_no_events():
    title, body = _format_summary([])
    assert title == "🌡️ FinSynapse"
    assert "无显著状态变化" in body


def test_format_summary_truncates_long_body():
    events = [
        Event(market="US", date="2026-04-29", kind="zone_crossing", summary="x" * 100, details={}) for _ in range(20)
    ]
    _, body = _format_summary(events)
    assert len(body) <= 800
    assert "truncated" in body


def test_send_bark_skipped_without_key(monkeypatch):
    monkeypatch.delenv("BARK_DEVICE_KEY", raising=False)
    from finsynapse import config as cfg

    cfg.settings = cfg.Settings()
    status, reason = send_bark("t", "b")
    assert status is None
    assert "BARK" in (reason or "")


def test_send_telegram_skipped_without_key(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    from finsynapse import config as cfg

    cfg.settings = cfg.Settings()
    status, reason = send_telegram("t")
    assert status is None
    assert "TELEGRAM" in (reason or "")


def test_dispatch_calls_both_when_events_present(monkeypatch):
    """When events exist and channels are configured, both should be hit once."""
    monkeypatch.setenv("BARK_DEVICE_KEY", "fake_key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "fake_chat")
    from finsynapse import config as cfg

    cfg.settings = cfg.Settings()

    with patch("finsynapse.notify.dispatch.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        events = [
            Event(market="HK", date="2026-04-28", kind="zone_crossing", summary="HK mid→hot 🔥 (65→73)", details={})
        ]
        result = dispatch(events)

    assert mock_post.call_count == 2
    assert result.bark_status == 200
    assert result.telegram_status == 200


def test_dispatch_skips_when_no_events(monkeypatch):
    monkeypatch.setenv("BARK_DEVICE_KEY", "fake_key")
    from finsynapse import config as cfg

    cfg.settings = cfg.Settings()

    with patch("finsynapse.notify.dispatch.requests.post") as mock_post:
        result = dispatch([])

    assert mock_post.call_count == 0
    assert "no events" in (result.bark_skipped_reason or "")
