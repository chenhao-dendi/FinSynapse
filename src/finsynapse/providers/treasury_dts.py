"""U.S. Treasury Daily Treasury Statement provider.

This official, keyless FiscalData source collects Treasury General Account
(TGA) operating-cash rows for future US liquidity research. The indicators are
not weighted in the production temperature model yet.

Source documentation:
    https://fiscaldata.treasury.gov/datasets/daily-treasury-statement/
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from finsynapse.providers.base import FetchRange, Provider
from finsynapse.providers.retry import requests_session

API_URL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/operating_cash_balance"
PAGE_SIZE = 10000


@dataclass(frozen=True)
class TreasuryDtsSeries:
    account_type: str
    indicator: str


MODERN_TGA_CLOSING = "Treasury General Account (TGA) Closing Balance"
MODERN_NON_BALANCE_ACCOUNTS = {
    "Treasury General Account (TGA) Opening Balance",
    "Total TGA Deposits (Table II)",
    "Total TGA Withdrawals (Table II) (-)",
}

FLOW_SERIES: tuple[TreasuryDtsSeries, ...] = (
    TreasuryDtsSeries(
        account_type="Total TGA Deposits (Table II)",
        indicator="us_tga_deposits",
    ),
    TreasuryDtsSeries(
        account_type="Total TGA Withdrawals (Table II) (-)",
        indicator="us_tga_withdrawals",
    ),
)


class TreasuryDtsProvider(Provider):
    name = "treasury_dts"
    layer = "macro"

    def fetch(self, fetch_range: FetchRange) -> pd.DataFrame:
        records = self._fetch_records(fetch_range)
        records["date"] = pd.to_datetime(records["record_date"], errors="coerce").dt.date
        records["value"] = pd.to_numeric(records["open_today_bal"], errors="coerce")

        rows: list[pd.DataFrame] = [self._balance_rows(records)]
        for series in FLOW_SERIES:
            sub = records[records["account_type"] == series.account_type].copy()
            if sub.empty:
                continue
            rows.append(
                pd.DataFrame(
                    {
                        "date": sub["date"],
                        "indicator": series.indicator,
                        "value": sub["value"],
                        "source_symbol": f"FiscalData/DTS/operating_cash_balance/{series.account_type}",
                    }
                ).dropna(subset=["date", "value"])
            )

        if not rows:
            raise RuntimeError(f"Treasury DTS returned 0 mapped rows for {fetch_range.start}..{fetch_range.end}")
        out = pd.concat(rows, ignore_index=True)
        out = out[(out["date"] >= fetch_range.start) & (out["date"] <= fetch_range.end)]
        if out.empty:
            raise RuntimeError(f"Treasury DTS returned 0 rows in range {fetch_range.start}..{fetch_range.end}")
        return out.sort_values(["indicator", "date"]).reset_index(drop=True)

    def _balance_rows(self, records: pd.DataFrame) -> pd.DataFrame:
        modern = records[records["account_type"] == MODERN_TGA_CLOSING][["date", "value"]].copy()
        modern["source_symbol"] = f"FiscalData/DTS/operating_cash_balance/{MODERN_TGA_CLOSING}"

        # Before the current TGA row layout, FiscalData exposes Table I as
        # operating-cash components (Federal Reserve Account, Tax and Loan,
        # Supplementary Financing Program, etc.). If no modern closing row
        # exists for a date, sum the component rows to preserve history.
        modern_dates = set(modern["date"].dropna())
        legacy = records[
            (~records["date"].isin(modern_dates)) & (~records["account_type"].isin(MODERN_NON_BALANCE_ACCOUNTS))
        ]
        legacy = (
            legacy.dropna(subset=["date"])
            .groupby("date", as_index=False)["value"]
            .sum(min_count=1)
            .dropna(subset=["value"])
        )
        legacy["source_symbol"] = "FiscalData/DTS/operating_cash_balance/legacy_operating_cash_sum"

        balance = pd.concat([modern, legacy], ignore_index=True)
        if balance.empty:
            return pd.DataFrame(columns=["date", "indicator", "value", "source_symbol"])
        balance["indicator"] = "us_tga_balance"
        return balance[["date", "indicator", "value", "source_symbol"]]

    def _fetch_records(self, fetch_range: FetchRange) -> pd.DataFrame:
        all_records: list[dict] = []
        page = 1
        total_pages = 1

        while page <= total_pages:
            params = {
                "fields": "record_date,account_type,open_today_bal",
                "filter": f"record_date:gte:{fetch_range.start},record_date:lte:{fetch_range.end}",
                "sort": "record_date,account_type",
                "page[number]": page,
                "page[size]": PAGE_SIZE,
            }
            r = requests_session().get(API_URL, params=params, timeout=(10, 30))
            r.raise_for_status()
            payload = r.json()
            records = payload.get("data", [])
            if not records and page == 1:
                raise RuntimeError("Treasury DTS returned no records")
            all_records.extend(records)

            meta = payload.get("meta", {})
            total_pages = int(meta.get("total-pages") or 1)
            page += 1

        return pd.DataFrame(all_records)


def run(fetch_range: FetchRange, fetch_date: date | None = None) -> tuple[pd.DataFrame, str]:
    provider = TreasuryDtsProvider()
    df = provider.fetch(fetch_range)
    path = provider.write_bronze(df, fetch_date or date.today())
    return df, str(path)
