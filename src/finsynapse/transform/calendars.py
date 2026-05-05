"""CN A-share market closure calendar.

Used to flag HK rows whose `cn_south_5d` (southbound 5-day net buy) input
is *expected* to be missing — Stock Connect southbound stops trading on
mainland public holidays. Without this flag we'd mark HK rows incomplete
and fall back the dashboard asof to the last pre-holiday date, even though
the absence is structural, not a data quality problem.

NOT a full trading calendar — only the multi-day closures that actually
matter for the dashboard's "latest publishable date" selection. Single-day
weekends are excluded (handled implicitly by the underlying daily data).

Update annually after CSRC/SSE publishes the next year's holiday schedule.
"""

from __future__ import annotations

from datetime import date


def _expand(start: str, end: str) -> set[date]:
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    out: set[date] = set()
    cur = s
    while cur <= e:
        out.add(cur)
        cur = date.fromordinal(cur.toordinal() + 1)
    return out


# Public holidays + adjacent observed-closure days for A-share / Stock Connect.
# Sources:
#   - SSE: https://english.sse.com.cn/markets/tradingmarket/calendar/
#   - HKEX Stock Connect calendar: https://www.hkex.com.hk/Mutual-Market/Stock-Connect/...
# Keep dates inclusive; weekend-only stretches inside a holiday block are
# already covered by the data being absent on weekends.
CN_MAINLAND_CLOSED_DATES: set[date] = (
    _expand("2024-01-01", "2024-01-01")  # New Year
    | _expand("2024-02-09", "2024-02-17")  # Spring Festival
    | _expand("2024-04-04", "2024-04-06")  # Qingming
    | _expand("2024-05-01", "2024-05-05")  # Labour Day
    | _expand("2024-06-08", "2024-06-10")  # Dragon Boat
    | _expand("2024-09-15", "2024-09-17")  # Mid-Autumn
    | _expand("2024-10-01", "2024-10-07")  # National Day
    | _expand("2025-01-01", "2025-01-01")
    | _expand("2025-01-28", "2025-02-04")  # Spring Festival
    | _expand("2025-04-04", "2025-04-06")
    | _expand("2025-05-01", "2025-05-05")
    | _expand("2025-05-31", "2025-06-02")  # Dragon Boat
    | _expand("2025-10-01", "2025-10-08")  # National Day + Mid-Autumn merged
    | _expand("2026-01-01", "2026-01-01")
    | _expand("2026-02-16", "2026-02-22")  # Spring Festival (provisional)
    | _expand("2026-04-04", "2026-04-06")  # Qingming (provisional)
    | _expand("2026-05-01", "2026-05-05")  # Labour Day
    | _expand("2026-06-19", "2026-06-21")  # Dragon Boat (provisional)
    | _expand("2026-09-25", "2026-09-27")  # Mid-Autumn (provisional)
    | _expand("2026-10-01", "2026-10-07")  # National Day (provisional)
)


def cn_mainland_closed(d: date) -> bool:
    """True if the CN A-share / Stock Connect southbound is closed on `d`.

    Conservative: returns False for any date outside the encoded range
    (older history or far future). Callers should treat the False case as
    "no special handling" rather than "definitely open".
    """
    return d in CN_MAINLAND_CLOSED_DATES
