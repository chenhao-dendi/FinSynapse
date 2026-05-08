from __future__ import annotations

from datetime import date

import pytest

from finsynapse.providers.hsi_monthly_valuation import (
    HsiMonthlyArchiveDiscovery,
    discover_hsi_monthly_roundup_archive,
    hsi_monthly_roundup_candidate_urls,
    hsi_monthly_roundup_url,
    parse_hsi_monthly_roundup_text,
    publication_months,
)


def test_hsi_monthly_roundup_url_uses_publication_date_stamp():
    url = hsi_monthly_roundup_url(date(2024, 12, 2))

    assert url.endswith("/20241202T000000.pdf")


def test_hsi_monthly_roundup_candidate_urls_scan_month_start():
    urls = hsi_monthly_roundup_candidate_urls(2024, 12, max_day=3)

    assert urls == [
        "https://www.hsi.com.hk/static/uploads/contents/en/dl_centre/monthly_roundup/20241201T000000.pdf",
        "https://www.hsi.com.hk/static/uploads/contents/en/dl_centre/monthly_roundup/20241202T000000.pdf",
        "https://www.hsi.com.hk/static/uploads/contents/en/dl_centre/monthly_roundup/20241203T000000.pdf",
    ]


def test_publication_months_cover_inclusive_range():
    assert publication_months(date(2024, 12, 15), date(2025, 2, 1)) == ((2024, 12), (2025, 1), (2025, 2))


def test_archive_discovery_reports_found_and_missing_months(monkeypatch):
    found = "https://www.hsi.com.hk/static/uploads/contents/en/dl_centre/monthly_roundup/20241202T000000.pdf"

    def fake_is_pdf_url(url: str, *, timeout: tuple[int, int]) -> bool:
        return url == found

    monkeypatch.setattr("finsynapse.providers.hsi_monthly_valuation._is_pdf_url", fake_is_pdf_url)

    discovery = discover_hsi_monthly_roundup_archive(((2024, 12), (2025, 1)), max_day=3)

    assert discovery == HsiMonthlyArchiveDiscovery(
        requested_months=((2024, 12), (2025, 1)),
        urls=(found,),
        missing_months=((2025, 1),),
    )


def test_parse_hsi_monthly_roundup_text_extracts_official_hsi_row():
    text = """
    Index Name                                                         1-Month 3-Month 12-Month     YTD     (Times)    Yield
    Hang Seng Index and its related indexes
    Hang Seng Index                                                    -4.40%    7.97%    13.97%   13.94%    11.31    3.78%
    Sub-Indexes
    Hang Seng Index - Finance                                          -3.57%     7.28%    14.31% 11.84%      7.06    5.73%
    """

    row = parse_hsi_monthly_roundup_text(
        text,
        "https://www.hsi.com.hk/static/uploads/contents/en/dl_centre/monthly_roundup/20241202T000000.pdf",
    )

    assert row.publication_date == "2024-12-02"
    assert row.pe_ratio == pytest.approx(11.31)
    assert row.dividend_yield == pytest.approx(3.78)


def test_parse_hsi_monthly_roundup_text_rejects_missing_hsi_row():
    with pytest.raises(ValueError, match="could not locate HSI"):
        parse_hsi_monthly_roundup_text("Index Name PE Ratio Dividend Yield", "https://example.test/no-row.pdf")
