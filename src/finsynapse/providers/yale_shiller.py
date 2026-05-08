"""Robert Shiller public market data from the online data workbook.

The production `us_cape` indicator currently comes from multpl because that
HTML table is simple and frequently updated.  This provider keeps Shiller's
own workbook as a collected-only audit series so CAPE research can compare the
vendor scrape against the underlying academic dataset without changing
temperature weights.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

from finsynapse.providers.base import FetchRange, Provider
from finsynapse.providers.retry import requests_session

LANDING_URL = "https://shillerdata.com/"
LEGACY_XLS_URL = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"
UA = {"User-Agent": "Mozilla/5.0 (FinSynapse data fetch)"}


@dataclass(frozen=True)
class ShillerWorkbookRow:
    date: date
    cape: float
    source_symbol: str


def discover_shiller_workbook_url(html: str, *, base_url: str = LANDING_URL) -> str:
    soup = BeautifulSoup(html, "lxml")
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"])
        if "ie_data.xls" in href.lower():
            return urljoin(base_url, href)
    raise RuntimeError("could not locate ie_data.xls link on Shiller data landing page")


def fetch_shiller_workbook_url() -> str:
    try:
        resp = requests_session().get(LANDING_URL, headers=UA, timeout=(10, 20))
        resp.raise_for_status()
        return discover_shiller_workbook_url(resp.text)
    except Exception:
        return LEGACY_XLS_URL


def parse_shiller_workbook(xls_bytes: bytes, source_url: str) -> pd.DataFrame:
    workbook = pd.read_excel(io.BytesIO(xls_bytes), sheet_name="Data", header=7)
    if "Date" not in workbook.columns or "CAPE" not in workbook.columns:
        raise RuntimeError("Shiller workbook missing required Date/CAPE columns")

    rows: list[ShillerWorkbookRow] = []
    for _, row in workbook[["Date", "CAPE"]].iterrows():
        month_start = _shiller_month_start(row["Date"])
        if month_start is None:
            continue
        cape = pd.to_numeric(row["CAPE"], errors="coerce")
        if pd.isna(cape):
            continue
        rows.append(
            ShillerWorkbookRow(
                date=month_start,
                cape=float(cape),
                source_symbol="ie_data.xls/CAPE",
            )
        )

    if not rows:
        raise RuntimeError(f"Shiller workbook parsed 0 CAPE rows from {source_url}")

    return pd.DataFrame(
        {
            "date": [row.date for row in rows],
            "indicator": "us_cape_shiller",
            "value": [row.cape for row in rows],
            "source_symbol": [row.source_symbol for row in rows],
        }
    ).sort_values("date")


class YaleShillerProvider(Provider):
    name = "yale_shiller"
    layer = "valuation"

    def fetch(self, fetch_range: FetchRange) -> pd.DataFrame:
        workbook_url = fetch_shiller_workbook_url()
        resp = requests_session().get(workbook_url, headers=UA, timeout=(10, 30))
        resp.raise_for_status()
        df = parse_shiller_workbook(resp.content, workbook_url)
        mask = (df["date"] >= fetch_range.start) & (df["date"] <= fetch_range.end)
        out = df[mask].reset_index(drop=True)
        if out.empty:
            raise RuntimeError(f"yale_shiller returned 0 rows in range {fetch_range.start}..{fetch_range.end}")
        return out


def _shiller_month_start(raw: object) -> date | None:
    if pd.isna(raw):
        return None
    if isinstance(raw, (int, float)):
        year = int(raw)
        month = round((float(raw) - year) * 100)
    else:
        text = str(raw).strip()
        match = re.fullmatch(r"(?P<year>\d{4})\.(?P<month>\d{1,2})", text)
        if not match:
            return None
        year = int(match.group("year"))
        month = int(match.group("month"))

    if month < 1 or month > 12:
        return None
    return date(year, month, 1)


def run(fetch_range: FetchRange, fetch_date: date | None = None) -> tuple[pd.DataFrame, str]:
    provider = YaleShillerProvider()
    df = provider.fetch(fetch_range)
    path = provider.write_bronze(df, fetch_date or date.today())
    return df, str(path)
