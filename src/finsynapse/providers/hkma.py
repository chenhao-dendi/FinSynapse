"""HKMA daily monetary base provider.

This is an official, keyless HKMA Open API source. The two indicators are
collected into bronze/silver for future HK liquidity research, but are not yet
weighted into the production temperature model.

Source documentation:
    https://apidocs.hkma.gov.hk/documentation/market-data-and-statistics/daily-monetary-statistics/daily-figures-monetary-base/
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from finsynapse.providers.base import FetchRange, Provider
from finsynapse.providers.retry import requests_session

API_URL = (
    "https://api.hkma.gov.hk/public/market-data-and-statistics/daily-monetary-statistics/daily-figures-monetary-base"
)


@dataclass(frozen=True)
class HkmaField:
    field: str
    indicator: str


FIELDS: tuple[HkmaField, ...] = (
    HkmaField(
        field="aggr_balance_af_disc_win",
        indicator="hk_aggregate_balance",
    ),
    HkmaField(
        field="mb_bf_disc_win_total",
        indicator="hk_monetary_base",
    ),
)


class HkmaMonetaryBaseProvider(Provider):
    name = "hkma_monetary_base"
    layer = "macro"

    def fetch(self, fetch_range: FetchRange) -> pd.DataFrame:
        records = self._fetch_all_records()
        rows: list[pd.DataFrame] = []
        for series in FIELDS:
            if series.field not in records.columns:
                raise KeyError(f"HKMA response missing `{series.field}`; columns={list(records.columns)}")

            sub = pd.DataFrame(
                {
                    "date": records["end_of_date"],
                    "indicator": series.indicator,
                    "value": pd.to_numeric(records[series.field], errors="coerce"),
                    "source_symbol": f"HKMA/daily-figures-monetary-base/{series.field}",
                }
            ).dropna(subset=["date", "value"])
            rows.append(sub)

        out = pd.concat(rows, ignore_index=True)
        out["date"] = pd.to_datetime(out["date"]).dt.date
        out = out[(out["date"] >= fetch_range.start) & (out["date"] <= fetch_range.end)]
        if out.empty:
            raise RuntimeError(f"HKMA monetary base returned 0 rows in range {fetch_range.start}..{fetch_range.end}")
        return out.sort_values(["indicator", "date"]).reset_index(drop=True)

    def _fetch_all_records(self) -> pd.DataFrame:
        # The endpoint currently has ~6.2k daily rows from 2002 onward; one
        # large pagesize keeps the provider deterministic and avoids offset
        # pagination drift while staying well inside the API's response size.
        r = requests_session().get(API_URL, params={"pagesize": 10000}, timeout=(10, 30))
        r.raise_for_status()
        payload = r.json()
        header = payload.get("header", {})
        if header.get("success") is not True:
            raise RuntimeError(f"HKMA API error: {header.get('err_code')} {header.get('err_msg')}")
        records = payload.get("result", {}).get("records", [])
        if not records:
            raise RuntimeError("HKMA monetary base returned no records")
        return pd.DataFrame(records)


def run(fetch_range: FetchRange, fetch_date: date | None = None) -> tuple[pd.DataFrame, str]:
    provider = HkmaMonetaryBaseProvider()
    df = provider.fetch(fetch_range)
    path = provider.write_bronze(df, fetch_date or date.today())
    return df, str(path)
