from __future__ import annotations

from pathlib import Path

import pandas as pd

from finsynapse import config as _cfg

# Default rolling windows (trading days). Monthly indicators (CAPE, PE) get
# upsampled to daily via forward-fill before the rolling window is applied.
WINDOWS = {
    "1y": 252,
    "5y": 252 * 5,
    "10y": 252 * 10,
}

# Indicators published less than daily must be ffill'd onto a business-day
# grid before percentile, otherwise rolling(252) sees ~12 (monthly) or ~52
# (weekly) points/yr and the percentile distribution is meaningless.
LOWFREQ_INDICATORS = {
    # monthly
    "us_cape",
    "us_pe_ttm",
    "cn_m2_yoy",
    "cn_social_financing_12m",
    "us_umich_sentiment",
    # weekly (FRED publishes Wed)
    "us_nfci",
    "us_walcl",
}

# Max business days to forward-fill a low-frequency indicator after its last
# source observation.  Beyond this, the value drops to NaN, letting the
# temperature layer's indicator ffill + coverage guard handle the gap.
#   monthly (US/global):   23 BDay ≈ 1 calendar month
#   monthly (CN macro):    60 BDay ≈ 3 calendar months (publication lag)
#   weekly:                 7 BDay ≈ 1.4 calendar weeks
# cn_social_financing_12m is kept at 23 BDay because the data source has been
# silent since Dec 2025; using 5-month-old data is worse than NaN.
LOWFREQ_FFILL_LIMITS: dict[str, int] = {
    "us_cape": 23,
    "us_pe_ttm": 23,
    "cn_m2_yoy": 60,
    "cn_social_financing_12m": 23,
    "us_umich_sentiment": 23,
    "us_nfci": 7,
    "us_walcl": 7,
}


def _to_daily(series: pd.Series, end: pd.Timestamp | None = None, limit: int | None = None) -> pd.Series:
    """Reindex a non-daily series onto a business-day grid via forward-fill.
    Series must be indexed by date (ascending). When `end` is provided (use the
    global silver max date), ffill carries the last known value forward — this
    matters for monthly indicators (M2, CAPE) that publish with lag.

    When `limit` is set, values more than `limit` business days past their
    nearest source observation are set to NaN. This prevents stale values from
    persisting across a missed publication cycle.
    """
    if series.empty:
        return series
    end_dt = end if end is not None else series.index.max()
    idx = pd.date_range(series.index.min(), end_dt, freq="B")
    # Always use method="ffill" to carry month-start values (often weekends)
    # onto the business-day grid.
    result = series.reindex(series.index.union(idx)).ffill().reindex(idx)
    if limit is not None:
        # Count consecutive BDay since last source observation.  Source dates
        # that fall on weekends/non-BDay are tracked via the union index.
        is_source = pd.Series(False, index=result.index)
        for sd in sorted(series.index):
            # Snap weekend source dates to the next BDay for staleness tracking
            bday_after = result.index[result.index >= sd]
            if len(bday_after) > 0:
                is_source.loc[bday_after[0]] = True
        # Build a cumulative counter that resets at each source
        stale = pd.Series(0, index=result.index, dtype=int)
        cnt = 0
        for i in range(len(result)):
            if is_source.iloc[i]:
                cnt = 0
            else:
                cnt += 1
            stale.iloc[i] = cnt
        result = result.where(stale <= limit)
    return result


def compute_percentiles(macro_long: pd.DataFrame) -> pd.DataFrame:
    """For each indicator, compute 1Y/5Y/10Y rolling percentile rank of the
    current value within its trailing window.

    Returns a long-format frame: date | indicator | value | pct_1y | pct_5y | pct_10y.
    """
    if macro_long.empty:
        return pd.DataFrame(columns=["date", "indicator", "value", "pct_1y", "pct_5y", "pct_10y"])

    # Global max date across all indicators — monthly series ffill up to here
    # so percentile/temperature have current values even when M2 lags by 2 months.
    global_max = pd.to_datetime(macro_long["date"]).max()

    out_frames: list[pd.DataFrame] = []
    for indicator, group in macro_long.groupby("indicator"):
        s = group.set_index(pd.to_datetime(group["date"]))["value"].sort_index()
        # Drop duplicate timestamps if any (e.g. same date from multiple sources after dedup)
        s = s[~s.index.duplicated(keep="last")]
        if indicator in LOWFREQ_INDICATORS:
            limit = LOWFREQ_FFILL_LIMITS.get(indicator)
            s = _to_daily(s, end=global_max, limit=limit)

        result = pd.DataFrame({"value": s})
        for label, window in WINDOWS.items():
            # rank='average' / pct=True gives the percentile of the LAST value
            # within the trailing window. min_periods avoids garbage early values.
            min_periods = max(60, window // 4)
            result[f"pct_{label}"] = s.rolling(window=window, min_periods=min_periods).apply(
                lambda x: (x.rank(pct=True).iloc[-1]) * 100.0, raw=False
            )

        result["indicator"] = indicator
        result["date"] = result.index.date
        out_frames.append(result.reset_index(drop=True))

    out = pd.concat(out_frames, ignore_index=True)
    return out[["date", "indicator", "value", "pct_1y", "pct_5y", "pct_10y"]]


def write_silver_percentile(df: pd.DataFrame) -> Path:
    silver = _cfg.settings.silver_dir
    silver.mkdir(parents=True, exist_ok=True)
    path = silver / "percentile_daily.parquet"
    df.to_parquet(path, index=False)
    return path
