"""Detect notable changes in the latest temperature row vs the previous one.

Per plan §16: only emit STATE CHANGES (zone crossings, sub-temp extremes),
never absolute thresholds. "VIX > 30" pings every correction; "CN crossed
into cold zone" pings once every 5 years and is unmissable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from finsynapse.dashboard.data import MARKETS, load


# Zone classifier (matches plan §11.3 / dashboard chart bands).
def zone(value: float) -> str:
    if pd.isna(value):
        return "unknown"
    if value < 30:
        return "cold"
    if value < 70:
        return "mid"
    return "hot"


SUB_NAMES = ("valuation", "sentiment", "liquidity")


@dataclass(frozen=True)
class Event:
    market: str
    date: str
    kind: str  # "zone_crossing" | "sub_extreme"
    summary: str
    details: dict


def _pick_meaningful_pair(sub: pd.DataFrame) -> tuple[pd.Series, pd.Series] | None:
    """Pick (yesterday, today) where BOTH rows have the same data_quality
    classification. Skips phantom rows where only ffill'd monthly data is
    present (would otherwise produce false zone crossings)."""
    sub = sub.dropna(subset=["overall"]).sort_values("date").reset_index(drop=True)
    if len(sub) < 2:
        return None
    sub["_completeness"] = sub[["valuation", "sentiment", "liquidity"]].notna().sum(axis=1)
    target = sub["_completeness"].max()
    qualified = sub[sub["_completeness"] == target]
    if len(qualified) < 2:
        # Only one historical row at the highest completeness — can't compare.
        # Fall back to second-best within last 30 rows.
        recent = sub.tail(30)
        # Take last two rows where completeness is the max found in `recent`.
        target = recent["_completeness"].max()
        qualified = recent[recent["_completeness"] == target]
        if len(qualified) < 2:
            return None
    return qualified.iloc[-2], qualified.iloc[-1]


def detect_changes() -> list[Event]:
    """Return all noteworthy events found in the latest silver/temperature."""
    data = load()
    if data.temperature.empty:
        return []

    events: list[Event] = []
    for market in MARKETS:
        sub = data.temperature[data.temperature["market"] == market]
        if sub.empty:
            continue
        pair = _pick_meaningful_pair(sub)
        if pair is None:
            continue
        yesterday, today = pair

        z_today = zone(today["overall"])
        z_yesterday = zone(yesterday["overall"])
        if z_today != z_yesterday and z_today != "unknown" and z_yesterday != "unknown":
            arrow = "🔥" if z_today == "hot" else ("🧊" if z_today == "cold" else "🌤")
            events.append(
                Event(
                    market=market.upper(),
                    date=str(today["date"]),
                    kind="zone_crossing",
                    summary=f"{market.upper()} {z_yesterday}→{z_today} {arrow} ({yesterday['overall']:.1f}°→{today['overall']:.1f}°)",
                    details={
                        "from_zone": z_yesterday,
                        "to_zone": z_today,
                        "from_overall": float(yesterday["overall"]),
                        "to_overall": float(today["overall"]),
                    },
                )
            )

        # Sub-temp extremes — emit once when crossing into the extreme band,
        # not every day it stays there. Compare today vs yesterday on each axis.
        for s in SUB_NAMES:
            t_val = today.get(s)
            y_val = yesterday.get(s)
            if pd.isna(t_val) or pd.isna(y_val):
                continue
            t_extreme = t_val < 10 or t_val > 90
            y_extreme = y_val < 10 or y_val > 90
            if t_extreme and not y_extreme:
                direction = "极冷" if t_val < 10 else "极热"
                events.append(
                    Event(
                        market=market.upper(),
                        date=str(today["date"]),
                        kind="sub_extreme",
                        summary=f"{market.upper()} {s} 进入{direction}区 ({t_val:.0f}°)",
                        details={"sub": s, "value": float(t_val), "prev_value": float(y_val)},
                    )
                )

    return events


def serialize(events: list[Event]) -> list[dict]:
    return [asdict(e) for e in events]
