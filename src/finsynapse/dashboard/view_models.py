from __future__ import annotations

import pandas as pd

from finsynapse.dashboard.data import MARKETS, DashboardData
from finsynapse.dashboard.i18n import (
    divergence_plain,
    indicator_plain_name,
    pair_plain_name,
    t,
    translate_div,
)

# Map of market code -> display metadata used by the redesigned card UI.
# Colours mirror the chart palette (charts.py) so a card and its embedded
# Plotly figures share one visual identity.
MARKET_META = {
    "cn": {"label": "🇨🇳 CN", "name_zh": "中国 A 股", "name_en": "China A-share", "accent": "navy"},
    "hk": {"label": "🇭🇰 HK", "name_zh": "香港", "name_en": "Hong Kong", "accent": "gold"},
    "us": {"label": "🇺🇸 US", "name_zh": "美国", "name_en": "United States", "accent": "coral"},
}


# Strength -> (risk bucket key, star count, accent token). Buckets calibrated
# against the empirical spread of strengths we see in silver: most days
# everything is < 0.01; > 0.5 is genuinely rare.
def _risk_bucket(strength: float) -> tuple[str, int, str]:
    if strength >= 0.5:
        return "risk_high", 4, "coral"
    if strength >= 0.1:
        return "risk_med", 3, "gold"
    if strength >= 0.01:
        return "risk_low", 2, "navy"
    return "risk_weak", 1, "navy"


def _zone_token(value: float | None) -> tuple[str, str]:
    """(zone_key, accent) for a 0-100 temperature."""
    if value is None or pd.isna(value):
        return "zone_mid", "gold"
    if value >= 70:
        return "zone_hot", "coral"
    if value < 30:
        return "zone_cold", "navy"
    return "zone_mid", "gold"


def _market_history_stats(temperature: pd.DataFrame) -> dict[str, dict]:
    """Compute per-market historical extrema and today's own-history rank."""
    if temperature.empty:
        return {}
    df = temperature.copy()
    df["date"] = pd.to_datetime(df["date"])
    out: dict[str, dict] = {}
    for market in MARKETS:
        sub = df[df["market"] == market].dropna(subset=["overall"]).sort_values("date")
        if sub.empty:
            continue
        today_row = sub.iloc[-1]
        today_temp = float(today_row["overall"])
        # Inclusive rank (<=) so today's value itself counts.
        today_pct = float((sub["overall"] <= today_temp).mean() * 100.0)
        idx_hot = sub["overall"].idxmax()
        idx_cold = sub["overall"].idxmin()
        out[market] = {
            "today_pct": today_pct,
            "today_date": today_row["date"].date(),
            "today_temp": today_temp,
            "hot_date": sub.loc[idx_hot, "date"].date(),
            "hot_temp": float(sub.loc[idx_hot, "overall"]),
            "cold_date": sub.loc[idx_cold, "date"].date(),
            "cold_temp": float(sub.loc[idx_cold, "overall"]),
        }
    return out


def _build_market_cards(
    latest: dict,
    data_quality: dict,
    lang: str,
    history_stats: dict[str, dict] | None = None,
    complete_dates: dict[str, str | None] | None = None,
) -> list[dict]:
    """Compose the per-market hero cards for the static dashboard."""
    history_stats = history_stats or {}
    complete_dates = complete_dates or {}
    cards = []
    for market in MARKETS:
        meta = MARKET_META[market]
        if market not in latest:
            cards.append({"market": market, "meta": meta, "missing": True})
            continue
        row = latest[market]
        overall = row.get("overall")
        zone_key, accent = _zone_token(overall)
        change_1w = row.get("overall_change_1w")
        sub_temps = []
        for sub_key in ("valuation", "sentiment", "liquidity"):
            v = row.get(sub_key)
            sub_temps.append(
                {
                    "key": sub_key,
                    "label": t(sub_key, lang),
                    "plain": t(f"{sub_key}_plain", lang),
                    "value": None if (v is None or pd.isna(v)) else float(v),
                    "contribution": (
                        None
                        if pd.isna(row.get(f"{sub_key}_contribution_1w"))
                        else float(row.get(f"{sub_key}_contribution_1w"))
                    ),
                }
            )
        hist = history_stats.get(market)
        history_widget = None
        if hist is not None:
            pct_int = round(hist["today_pct"])
            history_widget = {
                "pct": pct_int,
                "hover": t("card_history_pct_hover", lang).format(pct=pct_int),
                "extremes_hint": t("card_history_extremes_hint", lang).format(
                    hot_temp=hist["hot_temp"], cold_temp=hist["cold_temp"]
                ),
            }
        completeness = row.get("subtemp_completeness")
        cards.append(
            {
                "market": market,
                "meta": meta,
                "missing": False,
                "asof": pd.to_datetime(row["date"]).date().isoformat(),
                "overall": float(overall) if overall is not None and not pd.isna(overall) else None,
                "overall_int": round(overall) if overall is not None and not pd.isna(overall) else None,
                "change_1w": None if (change_1w is None or pd.isna(change_1w)) else float(change_1w),
                "zone_label": t(f"{zone_key}_label", lang),
                "zone_key": zone_key,
                "accent": accent,
                "sub_temps": sub_temps,
                "data_quality": data_quality.get(market, "ok"),
                "history": history_widget,
                "latest_complete_date": complete_dates.get(market),
                "subtemp_completeness": int(completeness)
                if completeness is not None and not pd.isna(completeness)
                else None,
            }
        )
    return cards


def _build_divergence_cards(div_df: pd.DataFrame, lang: str, limit: int = 6) -> list[dict]:
    """Build user-facing cards for active divergence signals."""
    if div_df.empty:
        return []
    df = div_df[div_df["is_divergent"]].copy()
    if df.empty:
        return []
    df["date"] = pd.to_datetime(df["date"])
    cutoff = df["date"].max() - pd.Timedelta(days=90)
    df = df[df["date"] >= cutoff].sort_values("strength", ascending=False)
    # De-duplicate by pair: keep the strongest occurrence of each pair so the
    # user sees breadth instead of one pair filling the page after repeated spikes.
    df = df.drop_duplicates(subset="pair_name", keep="first").head(limit)

    cards = []
    for _, d in df.iterrows():
        pair = d["pair_name"]
        strength = float(d["strength"])
        bucket_key, stars, accent = _risk_bucket(strength)
        cards.append(
            {
                "date": d["date"].date().isoformat(),
                "pair_code": pair,
                "pair_plain": pair_plain_name(pair, lang),
                "headline": translate_div(d["description"], lang),
                "plain_explanation": divergence_plain(d["description"], lang),
                "strength": strength,
                "stars": stars,
                "stars_empty": 4 - stars,
                "risk_label": t(bucket_key, lang),
                "accent": accent,
                "a_change_pct": float(d["a_change"]) * 100,
                "b_change_pct": float(d["b_change"]) * 100,
            }
        )
    return cards


def _build_key_takeaways(data: DashboardData, latest: dict, div_cards: list[dict], lang: str) -> list[dict]:
    """Produce up to 3 deterministic structured takeaways."""
    out: list[dict] = []

    rated = [
        (m, row.get("overall"), row.get("overall_change_1w"))
        for m, row in latest.items()
        if row.get("overall") is not None and not pd.isna(row.get("overall"))
    ]
    if rated:
        # Pick whichever is further from neutral (50).
        m, v, chg = max(rated, key=lambda x: abs(x[1] - 50))
        zone_key, accent = _zone_token(v)
        meta = MARKET_META[m]
        market_name = meta["name_zh"] if lang == "zh" else meta["name_en"]
        if lang == "zh":
            chg_phrase = ""
            if chg is not None and not pd.isna(chg) and abs(chg) >= 0.5:
                direction = "升" if chg > 0 else "降"
                chg_phrase = f"，本周{direction} {abs(chg):.1f}°"
            detail = f"温度 {v:.0f}°，处于{t(zone_key, lang)}区间{chg_phrase}。"
        else:
            chg_phrase = ""
            if chg is not None and not pd.isna(chg) and abs(chg) >= 0.5:
                direction = "up" if chg > 0 else "down"
                chg_phrase = f", {direction} {abs(chg):.1f}° this week"
            detail = f"Temperature {v:.0f}°, in the {t(zone_key, lang)} zone{chg_phrase}."
        out.append(
            {
                "icon": "thermostat",
                "accent": accent,
                "headline": (
                    f"{meta['label']} {market_name} 最值得关注"
                    if lang == "zh"
                    else f"{meta['label']} {market_name} is the standout"
                ),
                "detail": detail,
            }
        )

    if div_cards:
        top = div_cards[0]
        out.append(
            {
                "icon": "call_split",
                "accent": top["accent"],
                "headline": top["pair_plain"],
                "detail": top["plain_explanation"] or top["headline"],
            }
        )

    if not data.percentile.empty:
        pct = data.percentile.copy()
        pct["date"] = pd.to_datetime(pct["date"])
        latest_dt = pct["date"].max()
        snap = pct[pct["date"] == latest_dt].dropna(subset=["pct_10y"])
        extreme = snap[(snap["pct_10y"] >= 90) | (snap["pct_10y"] <= 10)]
        if not extreme.empty:
            extreme = extreme.assign(_dist=lambda d: (d["pct_10y"] - 50).abs())
            top = extreme.sort_values("_dist", ascending=False).iloc[0]
            ind = top["indicator"]
            plain = indicator_plain_name(ind, lang)
            pct_val = float(top["pct_10y"])
            is_high = pct_val >= 90
            accent = "coral" if is_high else "navy"
            if lang == "zh":
                headline = f"{plain} 处于 10 年 {pct_val:.0f}% 分位"
                detail = f"当前值 {top['value']:.4g}，{'已到极端高位' if is_high else '已到极端低位'} — `{ind}`。"
            else:
                headline = f"{plain} sits at {pct_val:.0f}-pct (10y)"
                detail = f"Current value {top['value']:.4g}, {'extreme high' if is_high else 'extreme low'} — `{ind}`."
            out.append({"icon": "monitoring", "accent": accent, "headline": headline, "detail": detail})

    return out[:3]
