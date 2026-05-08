"""Official Hang Seng Index monthly valuation from HSI Monthly Roundup PDFs.

This source collects index-level PE ratio and dividend yield from Hang Seng
Indexes' Monthly Roundup PDF archive. It is intentionally collected-only:
monthly PDF archive crawling is useful for research/backfill, but should not
change HK production temperature weights until parser/backtest review passes.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from finsynapse.providers.base import FetchRange, Provider
from finsynapse.providers.retry import requests_session

MONTHLY_ROUNDUP_BASE_URL = "https://www.hsi.com.hk/static/uploads/contents/en/dl_centre/monthly_roundup"
DEFAULT_MAX_PUBLICATION_DAY = 7

HSI_MONTHLY_ROW_RE = re.compile(
    r"Hang Seng Index\s+"
    r"(?P<month>-?\d+(?:\.\d+)?%)\s+"
    r"(?P<three_month>-?\d+(?:\.\d+)?%)\s+"
    r"(?P<twelve_month>-?\d+(?:\.\d+)?%)\s+"
    r"(?P<ytd>-?\d+(?:\.\d+)?%)\s+"
    r"(?P<pe>\d+(?:\.\d+)?)\s+"
    r"(?P<dividend_yield>\d+(?:\.\d+)?)%"
)


@dataclass(frozen=True)
class HsiMonthlyValuation:
    publication_date: str
    pe_ratio: float
    dividend_yield: float
    source_url: str


@dataclass(frozen=True)
class HsiMonthlyArchiveDiscovery:
    requested_months: tuple[tuple[int, int], ...]
    urls: tuple[str, ...]
    missing_months: tuple[tuple[int, int], ...]


def hsi_monthly_roundup_url(publication_date: date) -> str:
    return f"{MONTHLY_ROUNDUP_BASE_URL}/{publication_date:%Y%m%d}T000000.pdf"


def hsi_monthly_roundup_candidate_urls(
    year: int,
    month: int,
    max_day: int = DEFAULT_MAX_PUBLICATION_DAY,
) -> list[str]:
    last_day = min(max_day, monthrange(year, month)[1])
    return [hsi_monthly_roundup_url(date(year, month, day)) for day in range(1, last_day + 1)]


def publication_months(start: date, end: date) -> tuple[tuple[int, int], ...]:
    if start > end:
        return ()
    months: list[tuple[int, int]] = []
    year = start.year
    month = start.month
    while (year, month) <= (end.year, end.month):
        months.append((year, month))
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
    return tuple(months)


def discover_hsi_monthly_roundup_urls(
    months: tuple[tuple[int, int], ...],
    *,
    max_day: int = DEFAULT_MAX_PUBLICATION_DAY,
    timeout: tuple[int, int] = (10, 20),
) -> list[str]:
    return list(discover_hsi_monthly_roundup_archive(months, max_day=max_day, timeout=timeout).urls)


def discover_hsi_monthly_roundup_archive(
    months: tuple[tuple[int, int], ...],
    *,
    max_day: int = DEFAULT_MAX_PUBLICATION_DAY,
    timeout: tuple[int, int] = (10, 20),
) -> HsiMonthlyArchiveDiscovery:
    urls: list[str] = []
    missing_months: list[tuple[int, int]] = []
    for year, month in months:
        found_url = None
        for url in hsi_monthly_roundup_candidate_urls(year, month, max_day=max_day):
            if _is_pdf_url(url, timeout=timeout):
                found_url = url
                break
        if found_url:
            urls.append(found_url)
        else:
            missing_months.append((year, month))
    return HsiMonthlyArchiveDiscovery(
        requested_months=months,
        urls=tuple(urls),
        missing_months=tuple(missing_months),
    )


def parse_hsi_monthly_roundup_text(text: str, source_url: str) -> HsiMonthlyValuation:
    match = HSI_MONTHLY_ROW_RE.search(text)
    if not match:
        raise ValueError("could not locate HSI PE/dividend-yield row in Monthly Roundup text")
    return HsiMonthlyValuation(
        publication_date=_publication_date_from_url(source_url),
        pe_ratio=float(match.group("pe")),
        dividend_yield=float(match.group("dividend_yield")),
        source_url=source_url,
    )


def fetch_hsi_monthly_roundup_valuation(url: str) -> HsiMonthlyValuation:
    resp = requests_session().get(url, timeout=(10, 30))
    resp.raise_for_status()
    text = extract_pdf_text(resp.content)
    return parse_hsi_monthly_roundup_text(text, url)


def extract_pdf_text(pdf_bytes: bytes, *, pdftotext_bin: str = "pdftotext") -> str:
    if not shutil.which(pdftotext_bin):
        raise RuntimeError(f"{pdftotext_bin} is required for HSI Monthly Roundup PDF parsing")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_bytes)
        pdf_path = Path(f.name)
    try:
        proc = subprocess.run(
            [pdftotext_bin, "-layout", str(pdf_path), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
        return proc.stdout
    finally:
        pdf_path.unlink(missing_ok=True)


def pdftotext_available(pdftotext_bin: str = "pdftotext") -> bool:
    return shutil.which(pdftotext_bin) is not None


class HsiMonthlyValuationProvider(Provider):
    name = "hsi_monthly_valuation"
    layer = "valuation"

    def fetch(self, fetch_range: FetchRange) -> pd.DataFrame:
        if not pdftotext_available():
            raise RuntimeError("pdftotext is required for hsi_monthly_valuation; install poppler-utils")

        urls = discover_hsi_monthly_roundup_urls(publication_months(fetch_range.start, fetch_range.end))
        rows: list[dict[str, object]] = []
        for url in urls:
            valuation = fetch_hsi_monthly_roundup_valuation(url)
            published = date.fromisoformat(valuation.publication_date)
            if published < fetch_range.start or published > fetch_range.end:
                continue
            rows.extend(
                [
                    {
                        "date": published,
                        "indicator": "hk_hsi_pe",
                        "value": valuation.pe_ratio,
                        "source_symbol": f"{Path(urlparse(url).path).name}/PE",
                    },
                    {
                        "date": published,
                        "indicator": "hk_hsi_dividend_yield",
                        "value": valuation.dividend_yield,
                        "source_symbol": f"{Path(urlparse(url).path).name}/DividendYield",
                    },
                ]
            )

        if not rows:
            raise RuntimeError(f"hsi_monthly_valuation returned 0 rows in range {fetch_range.start}..{fetch_range.end}")
        return pd.DataFrame(rows).sort_values(["indicator", "date"]).reset_index(drop=True)


def _publication_date_from_url(source_url: str) -> str:
    name = Path(urlparse(source_url).path).name
    match = re.match(r"(?P<yyyymmdd>\d{8})T\d{6}\.pdf", name)
    if not match:
        return "unknown"
    raw = match.group("yyyymmdd")
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def _is_pdf_url(url: str, *, timeout: tuple[int, int]) -> bool:
    try:
        resp = requests_session().head(url, allow_redirects=True, timeout=timeout)
    except Exception:
        return False
    return resp.status_code == 200 and "application/pdf" in resp.headers.get("content-type", "").lower()


def run(fetch_range: FetchRange, fetch_date: date | None = None) -> tuple[pd.DataFrame, str]:
    provider = HsiMonthlyValuationProvider()
    df = provider.fetch(fetch_range)
    path = provider.write_bronze(df, fetch_date or date.today())
    return df, str(path)
