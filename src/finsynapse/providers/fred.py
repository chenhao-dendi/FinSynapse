from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd
import requests

from finsynapse.config import settings
from finsynapse.providers.base import FetchRange, Provider


@dataclass(frozen=True)
class FredSeries:
    series_id: str
    indicator: str  # canonical name


# Series chosen for Phase 1: US 10Y real rate is the headline liquidity input.
# Add CPI / unemployment in Phase 1b when CN providers are also wired in.
SERIES: tuple[FredSeries, ...] = (FredSeries(series_id="DFII10", indicator="us10y_real_yield"),)

API_BASE = "https://api.stlouisfed.org/fred/series/observations"


class FredProvider(Provider):
    name = "fred"
    layer = "macro"

    def fetch(self, fetch_range: FetchRange) -> pd.DataFrame:
        if not settings.fred_api_key:
            raise RuntimeError(
                "FRED_API_KEY not configured. Get a free key at "
                "https://fred.stlouisfed.org/docs/api/api_key.html and put it in .env"
            )

        frames: list[pd.DataFrame] = []
        for series in SERIES:
            df = self._fetch_one(series, fetch_range)
            frames.append(df)
        out = pd.concat(frames, ignore_index=True)
        if out.empty:
            raise RuntimeError(f"FRED returned 0 rows for {fetch_range.start}..{fetch_range.end}")
        return out.sort_values(["indicator", "date"]).reset_index(drop=True)

    def _fetch_one(self, series: FredSeries, fetch_range: FetchRange) -> pd.DataFrame:
        params = {
            "series_id": series.series_id,
            "api_key": settings.fred_api_key,
            "file_type": "json",
            "observation_start": fetch_range.start.isoformat(),
            "observation_end": fetch_range.end.isoformat(),
        }
        r = requests.get(API_BASE, params=params, timeout=30)
        r.raise_for_status()
        payload = r.json()
        observations = payload.get("observations", [])

        rows = []
        for obs in observations:
            value_str = obs.get("value", ".")
            if value_str in (".", "", None):  # FRED uses '.' for missing
                continue
            try:
                value = float(value_str)
            except ValueError:
                continue
            rows.append(
                {
                    "date": pd.to_datetime(obs["date"]).date(),
                    "indicator": series.indicator,
                    "value": value,
                    "source_symbol": series.series_id,
                }
            )

        return pd.DataFrame(rows)


def run(fetch_range: FetchRange, fetch_date: date | None = None) -> tuple[pd.DataFrame, str]:
    provider = FredProvider()
    df = provider.fetch(fetch_range)
    path = provider.write_bronze(df, fetch_date or date.today())
    return df, str(path)
