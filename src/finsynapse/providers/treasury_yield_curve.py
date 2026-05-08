"""US Treasury daily nominal yield curve.

This official, keyless source collects the nominal 3M and 10Y par yield
curve, plus the derived 10Y-3M spread. It provides a Treasury-native
cross-check/fallback for yfinance `^TNX` and FRED `T10Y3M`.

Source:
    https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date

import pandas as pd

from finsynapse.providers.base import FetchRange, Provider
from finsynapse.providers.retry import requests_session

UA = {"User-Agent": "Mozilla/5.0 (FinSynapse data fetch)"}
BASE = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{year}/all"
PARAMS = {"type": "daily_treasury_yield_curve", "_format": "csv"}


@dataclass(frozen=True)
class _Series:
    csv_column: str
    indicator: str


SERIES: tuple[_Series, ...] = (
    _Series(csv_column="3 Mo", indicator="us3m_yield"),
    _Series(csv_column="10 Yr", indicator="us10y_yield"),
)


class TreasuryYieldCurveProvider(Provider):
    name = "treasury_yield_curve"
    layer = "macro"

    def fetch(self, fetch_range: FetchRange) -> pd.DataFrame:
        years = range(fetch_range.start.year, fetch_range.end.year + 1)
        frames: list[pd.DataFrame] = []
        for y in years:
            try:
                frames.append(self._fetch_year(y))
            except Exception as exc:
                # Nominal Treasury curve data is available from 1990 onward on
                # the current CSV endpoint. Older windows can be requested by
                # historical backtests, so skip pre-1990 empty years.
                if y >= 1990:
                    raise RuntimeError(f"treasury yield curve {y}: {exc}") from exc

        if not frames:
            raise RuntimeError(f"treasury yield curve: 0 rows for {years.start}..{years.stop - 1}")
        df = pd.concat(frames, ignore_index=True)
        df = df[(df["date"] >= fetch_range.start) & (df["date"] <= fetch_range.end)]
        if df.empty:
            raise RuntimeError(f"treasury yield curve: 0 rows in window {fetch_range.start}..{fetch_range.end}")
        return df.sort_values(["indicator", "date"]).reset_index(drop=True)

    def _fetch_year(self, year: int) -> pd.DataFrame:
        url = BASE.format(year=year)
        params = {**PARAMS, "field_tdr_date_value": str(year)}
        r = requests_session().get(url, params=params, headers=UA, timeout=(10, 30))
        r.raise_for_status()
        raw = pd.read_csv(io.StringIO(r.text))
        if raw.empty or "Date" not in raw.columns:
            return pd.DataFrame(columns=["date", "indicator", "value", "source_symbol"])

        raw["date"] = pd.to_datetime(raw["Date"], format="%m/%d/%Y", errors="coerce").dt.date
        rows: list[pd.DataFrame] = []
        by_indicator: dict[str, pd.Series] = {}
        for series in SERIES:
            if series.csv_column not in raw.columns:
                continue
            values = pd.to_numeric(raw[series.csv_column], errors="coerce")
            by_indicator[series.indicator] = values
            sub = pd.DataFrame(
                {
                    "date": raw["date"],
                    "indicator": series.indicator,
                    "value": values,
                    "source_symbol": f"USTREAS:{series.csv_column.replace(' ', '')}",
                }
            ).dropna(subset=["date", "value"])
            rows.append(sub)

        if {"us10y_yield", "us3m_yield"}.issubset(by_indicator):
            spread = by_indicator["us10y_yield"] - by_indicator["us3m_yield"]
            rows.append(
                pd.DataFrame(
                    {
                        "date": raw["date"],
                        "indicator": "us_t10y3m",
                        "value": spread,
                        "source_symbol": "USTREAS:10Yr-3Mo",
                    }
                ).dropna(subset=["date", "value"])
            )

        if not rows:
            return pd.DataFrame(columns=["date", "indicator", "value", "source_symbol"])
        return pd.concat(rows, ignore_index=True)


def run(fetch_range: FetchRange, fetch_date: date | None = None) -> tuple[pd.DataFrame, str]:
    provider = TreasuryYieldCurveProvider()
    df = provider.fetch(fetch_range)
    path = provider.write_bronze(df, fetch_date or date.today())
    return df, str(path)
