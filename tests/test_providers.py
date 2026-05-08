"""Tests for providers not covered by test_yfinance_macro.py.

Tests focus on parsing logic and schema correctness — upstream responses are mocked
so tests never hit the network and are deterministic.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from finsynapse.providers.base import FetchRange
from finsynapse.providers.fred import SERIES as FRED_SERIES
from finsynapse.providers.fred import FredProvider
from finsynapse.providers.hkma import HkmaMonetaryBaseProvider
from finsynapse.providers.hsi_monthly_valuation import HsiMonthlyValuation, HsiMonthlyValuationProvider
from finsynapse.providers.multpl import MultplProvider
from finsynapse.providers.treasury_dts import TreasuryDtsProvider
from finsynapse.providers.treasury_real_yield import TreasuryRealYieldProvider
from finsynapse.providers.treasury_yield_curve import TreasuryYieldCurveProvider
from finsynapse.providers.yale_shiller import (
    YaleShillerProvider,
    discover_shiller_workbook_url,
    parse_shiller_workbook,
)
from finsynapse.providers.yfinance_hk import YFinanceHkValuationProvider

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _mock_response(json_data=None, text="", status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    resp.raise_for_status = lambda: None
    return resp


# ---------------------------------------------------------------------------
# fred
# ---------------------------------------------------------------------------

FRED_FIXTURE = {
    "observations": [
        {"date": "2026-04-01", "value": "2.15"},
        {"date": "2026-04-02", "value": "2.18"},
        {"date": "2026-04-03", "value": "."},
        {"date": "2026-04-04", "value": "2.20"},
    ]
}


def _fred_df(start=date(2026, 4, 1), end=date(2026, 4, 4)):
    with patch("finsynapse.providers.fred.requests_session") as mock_session:
        mock_session.return_value.get.return_value = _mock_response(json_data=FRED_FIXTURE)
        provider = FredProvider()
        return provider.fetch(FetchRange(start=start, end=end))


@pytest.fixture
def fred_env(tmp_data_dir, monkeypatch):
    """Inject FRED_API_KEY and rebuild settings so the provider can run."""
    monkeypatch.setenv("FRED_API_KEY", "test-key")
    from finsynapse import config as cfg

    monkeypatch.setattr(cfg, "settings", cfg.Settings())
    return tmp_data_dir


class TestFred:
    def test_parses_observations_into_long_schema(self, fred_env):
        df = _fred_df()
        assert set(df.columns) == {"date", "indicator", "value", "source_symbol"}
        assert len(df) > 0
        assert df["value"].notna().all()

    def test_skips_missing_dot_values(self, fred_env):
        df = _fred_df()
        dates = {str(d) for d in df["date"]}
        assert "2026-04-03" not in dates

    def test_empty_response_raises(self, fred_env):
        with patch("finsynapse.providers.fred.requests_session") as mock_session:
            mock_session.return_value.get.return_value = _mock_response(json_data={"observations": []})
            provider = FredProvider()
            with pytest.raises(RuntimeError):
                provider.fetch(FetchRange(start=date(2026, 4, 1), end=date(2026, 4, 1)))

    def test_bronze_write_idempotent(self, fred_env):
        df = _fred_df()
        provider = FredProvider()
        p1 = provider.write_bronze(df, date(2026, 4, 4))
        p2 = provider.write_bronze(df, date(2026, 4, 4))
        assert p1 == p2
        assert p1.exists()
        assert p1.name == "2026-04-04.parquet"

    def test_each_series_has_canonical_columns(self):
        for s in FRED_SERIES:
            assert s.indicator
            assert isinstance(s.indicator, str)

    def test_collects_yield_curve_spread_candidate(self, fred_env):
        df = _fred_df()
        assert "us_t10y3m" in set(df["indicator"])

    def test_collects_long_history_credit_spread_candidate(self, fred_env):
        df = _fred_df()
        assert "us_baa10y_spread" in set(df["indicator"])

    def test_collects_reverse_repo_liquidity_candidate(self, fred_env):
        df = _fred_df()
        assert "us_on_rrp" in set(df["indicator"])

    def test_collects_reserve_balance_liquidity_candidate(self, fred_env):
        df = _fred_df()
        assert "us_reserve_balances" in set(df["indicator"])

    def test_collects_official_overnight_funding_candidates(self, fred_env):
        df = _fred_df()
        assert {"us_effr", "us_sofr"}.issubset(set(df["indicator"]))


# ---------------------------------------------------------------------------
# multpl
# ---------------------------------------------------------------------------

MULTIPL_HTML = """<html><body>
<table id="datatable"><tr><th>Date</th></tr>
<tr><td>Apr 1, 2026</td><td>32.50</td></tr>
<tr><td>Mar 1, 2026</td><td>31.80</td></tr>
<tr><td>Feb 1, 2026</td><td>30.20</td></tr>
</table></body></html>"""


def _mock_multpl_get(url, headers=None, timeout=None):
    return _mock_response(text=MULTIPL_HTML)


class TestMultpl:
    def test_parses_html_table_into_long_schema(self, tmp_data_dir):
        with patch("finsynapse.providers.multpl.requests_session") as mock_session:
            mock_session.return_value.get.side_effect = _mock_multpl_get
            provider = MultplProvider()
            df = provider.fetch(FetchRange(start=date(2020, 1, 1), end=date(2026, 12, 31)))
        assert set(df.columns) == {"date", "indicator", "value", "source_symbol"}
        assert len(df) > 0
        assert df["value"].notna().all()

    def test_filters_to_requested_range(self, tmp_data_dir):
        with patch("finsynapse.providers.multpl.requests_session") as mock_session:
            mock_session.return_value.get.side_effect = _mock_multpl_get
            provider = MultplProvider()
            df = provider.fetch(FetchRange(start=date(2026, 3, 1), end=date(2026, 3, 31)))
        assert all(d.month == 3 for d in df["date"])
        assert all(d.year == 2026 for d in df["date"])

    def test_empty_html_raises(self, tmp_data_dir):
        with patch("finsynapse.providers.multpl.requests_session") as mock_session:
            mock_session.return_value.get.return_value = _mock_response(text="<html><body></body></html>")
            provider = MultplProvider()
            with pytest.raises(RuntimeError):
                provider.fetch(FetchRange(start=date(2026, 4, 1), end=date(2026, 4, 1)))

    def test_bronze_write_idempotent(self, tmp_data_dir):
        with patch("finsynapse.providers.multpl.requests_session") as mock_session:
            mock_session.return_value.get.side_effect = _mock_multpl_get
            provider = MultplProvider()
            df = provider.fetch(FetchRange(start=date(2020, 1, 1), end=date(2026, 12, 31)))
        p1 = provider.write_bronze(df, date(2026, 4, 1))
        p2 = provider.write_bronze(df, date(2026, 4, 1))
        assert p1 == p2
        assert p1.exists()


# ---------------------------------------------------------------------------
# Yale/Shiller workbook
# ---------------------------------------------------------------------------


SHILLER_WORKBOOK_FIXTURE = pd.DataFrame(
    {
        "Date": [2024.12, "2025.01", "May price is May 5th close"],
        "CAPE": [37.8, "38.2", None],
    }
)


class TestYaleShiller:
    def test_discovers_current_workbook_link_from_landing_page(self):
        html = '<html><body><a href="/downloads/ie_data.xls?ver=1">Online Data</a></body></html>'

        url = discover_shiller_workbook_url(html, base_url="https://shillerdata.com/")

        assert url == "https://shillerdata.com/downloads/ie_data.xls?ver=1"

    def test_parses_workbook_into_collected_only_cape_indicator(self):
        with patch("finsynapse.providers.yale_shiller.pd.read_excel", return_value=SHILLER_WORKBOOK_FIXTURE):
            df = parse_shiller_workbook(b"ignored", "https://shillerdata.com/ie_data.xls")

        assert set(df.columns) == {"date", "indicator", "value", "source_symbol"}
        assert df["date"].tolist() == [date(2024, 12, 1), date(2025, 1, 1)]
        assert (df["indicator"] == "us_cape_shiller").all()
        assert df["value"].tolist() == [37.8, 38.2]

    def test_fetch_filters_to_requested_range(self, tmp_data_dir):
        with (
            patch(
                "finsynapse.providers.yale_shiller.fetch_shiller_workbook_url",
                return_value="https://example.test/ie_data.xls",
            ),
            patch("finsynapse.providers.yale_shiller.requests_session") as mock_session,
            patch("finsynapse.providers.yale_shiller.pd.read_excel", return_value=SHILLER_WORKBOOK_FIXTURE),
        ):
            mock_session.return_value.get.return_value = _mock_response(text="", status_code=200)
            mock_session.return_value.get.return_value.content = b"ignored"
            provider = YaleShillerProvider()
            df = provider.fetch(FetchRange(start=date(2025, 1, 1), end=date(2025, 12, 31)))

        assert len(df) == 1
        assert df.iloc[0]["date"] == date(2025, 1, 1)
        assert df.iloc[0]["indicator"] == "us_cape_shiller"


# ---------------------------------------------------------------------------
# treasury_real_yield
# ---------------------------------------------------------------------------

TREASURY_CSV = """Date,10 YR
04/29/2026,2.42
04/28/2026,2.40
04/27/2026,2.41
"""


def _mock_treasury_get(url, params=None, headers=None, timeout=None):
    return _mock_response(text=TREASURY_CSV)


class TestTreasuryRealYield:
    def test_parses_csv_into_long_schema(self, tmp_data_dir):
        with patch("finsynapse.providers.treasury_real_yield.requests_session") as mock_session:
            mock_session.return_value.get.side_effect = _mock_treasury_get
            provider = TreasuryRealYieldProvider()
            df = provider.fetch(FetchRange(start=date(2026, 4, 27), end=date(2026, 4, 29)))
        assert set(df.columns) == {"date", "indicator", "value", "source_symbol"}
        assert len(df) == 3
        assert (df["indicator"] == "us10y_real_yield").all()

    def test_bronze_write_idempotent(self, tmp_data_dir):
        with patch("finsynapse.providers.treasury_real_yield.requests_session") as mock_session:
            mock_session.return_value.get.side_effect = _mock_treasury_get
            provider = TreasuryRealYieldProvider()
            df = provider.fetch(FetchRange(start=date(2026, 4, 27), end=date(2026, 4, 29)))
        p1 = provider.write_bronze(df, date(2026, 4, 29))
        p2 = provider.write_bronze(df, date(2026, 4, 29))
        assert p1 == p2
        assert p1.exists()


# ---------------------------------------------------------------------------
# treasury_yield_curve
# ---------------------------------------------------------------------------

TREASURY_YIELD_CURVE_CSV = """Date,"1 Mo","3 Mo","10 Yr","30 Yr"
04/29/2026,3.90,3.95,4.40,4.85
04/28/2026,3.91,3.96,4.38,4.83
04/27/2026,3.92,3.97,4.35,4.80
"""


def _mock_treasury_yield_curve_get(url, params=None, headers=None, timeout=None):
    return _mock_response(text=TREASURY_YIELD_CURVE_CSV)


class TestTreasuryYieldCurve:
    def test_parses_nominal_curve_and_spread(self, tmp_data_dir):
        with patch("finsynapse.providers.treasury_yield_curve.requests_session") as mock_session:
            mock_session.return_value.get.side_effect = _mock_treasury_yield_curve_get
            provider = TreasuryYieldCurveProvider()
            df = provider.fetch(FetchRange(start=date(2026, 4, 28), end=date(2026, 4, 29)))

        assert set(df.columns) == {"date", "indicator", "value", "source_symbol"}
        assert set(df["indicator"]) == {"us3m_yield", "us10y_yield", "us_t10y3m"}
        assert len(df) == 6
        spread = df[(df["date"] == date(2026, 4, 29)) & (df["indicator"] == "us_t10y3m")]["value"].iloc[0]
        assert spread == pytest.approx(0.45)

    def test_bronze_write_idempotent(self, tmp_data_dir):
        with patch("finsynapse.providers.treasury_yield_curve.requests_session") as mock_session:
            mock_session.return_value.get.side_effect = _mock_treasury_yield_curve_get
            provider = TreasuryYieldCurveProvider()
            df = provider.fetch(FetchRange(start=date(2026, 4, 28), end=date(2026, 4, 29)))

        p1 = provider.write_bronze(df, date(2026, 4, 29))
        p2 = provider.write_bronze(df, date(2026, 4, 29))
        assert p1 == p2
        assert p1.exists()


# ---------------------------------------------------------------------------
# treasury DTS operating cash balance
# ---------------------------------------------------------------------------

TREASURY_DTS_FIXTURE = {
    "data": [
        {
            "record_date": "2026-05-01",
            "account_type": "Total TGA Deposits (Table II)",
            "open_today_bal": "43050",
        },
        {
            "record_date": "2026-05-01",
            "account_type": "Total TGA Withdrawals (Table II) (-)",
            "open_today_bal": "155122",
        },
        {
            "record_date": "2026-05-01",
            "account_type": "Treasury General Account (TGA) Closing Balance",
            "open_today_bal": "857311",
        },
        {
            "record_date": "2026-05-04",
            "account_type": "Total TGA Deposits (Table II)",
            "open_today_bal": "39449",
        },
        {
            "record_date": "2026-05-04",
            "account_type": "Total TGA Withdrawals (Table II) (-)",
            "open_today_bal": "16792",
        },
        {
            "record_date": "2026-05-04",
            "account_type": "Treasury General Account (TGA) Closing Balance",
            "open_today_bal": "879968",
        },
    ],
    "meta": {"total-pages": 1},
}


TREASURY_DTS_LEGACY_FIXTURE = {
    "data": [
        {
            "record_date": "2010-01-04",
            "account_type": "Federal Reserve Account",
            "open_today_bal": "186632",
        },
        {
            "record_date": "2010-01-04",
            "account_type": "Financial Institution Accoun",
            "open_today_bal": "0",
        },
        {
            "record_date": "2010-01-04",
            "account_type": "Supplementary Financing Prog",
            "open_today_bal": "5001",
        },
        {
            "record_date": "2010-01-04",
            "account_type": "Tax and Loan Note Accounts (Table V)",
            "open_today_bal": "1962",
        },
    ],
    "meta": {"total-pages": 1},
}


class TestTreasuryDts:
    def test_parses_tga_operating_cash_rows(self, tmp_data_dir):
        with patch("finsynapse.providers.treasury_dts.requests_session") as mock_session:
            mock_session.return_value.get.return_value = _mock_response(json_data=TREASURY_DTS_FIXTURE)
            provider = TreasuryDtsProvider()
            df = provider.fetch(FetchRange(start=date(2026, 5, 1), end=date(2026, 5, 4)))

        assert set(df.columns) == {"date", "indicator", "value", "source_symbol"}
        assert set(df["indicator"]) == {"us_tga_balance", "us_tga_deposits", "us_tga_withdrawals"}
        assert len(df) == 6
        balance = df[(df["date"] == date(2026, 5, 1)) & (df["indicator"] == "us_tga_balance")]["value"].iloc[0]
        assert balance == pytest.approx(857311)

    def test_derives_legacy_operating_cash_balance(self, tmp_data_dir):
        with patch("finsynapse.providers.treasury_dts.requests_session") as mock_session:
            mock_session.return_value.get.return_value = _mock_response(json_data=TREASURY_DTS_LEGACY_FIXTURE)
            provider = TreasuryDtsProvider()
            df = provider.fetch(FetchRange(start=date(2010, 1, 4), end=date(2010, 1, 4)))

        assert set(df["indicator"]) == {"us_tga_balance"}
        assert df["value"].iloc[0] == pytest.approx(193595)
        assert df["source_symbol"].iloc[0].endswith("/legacy_operating_cash_sum")

    def test_paginates_fiscaldata_response(self, tmp_data_dir):
        first_page = {
            "data": TREASURY_DTS_FIXTURE["data"][:3],
            "meta": {"total-pages": 2},
        }
        second_page = {
            "data": TREASURY_DTS_FIXTURE["data"][3:],
            "meta": {"total-pages": 2},
        }
        with patch("finsynapse.providers.treasury_dts.requests_session") as mock_session:
            mock_session.return_value.get.side_effect = [
                _mock_response(json_data=first_page),
                _mock_response(json_data=second_page),
            ]
            provider = TreasuryDtsProvider()
            df = provider.fetch(FetchRange(start=date(2026, 5, 1), end=date(2026, 5, 4)))

        assert len(df) == 6
        assert mock_session.return_value.get.call_count == 2

    def test_bronze_write_idempotent(self, tmp_data_dir):
        with patch("finsynapse.providers.treasury_dts.requests_session") as mock_session:
            mock_session.return_value.get.return_value = _mock_response(json_data=TREASURY_DTS_FIXTURE)
            provider = TreasuryDtsProvider()
            df = provider.fetch(FetchRange(start=date(2026, 5, 1), end=date(2026, 5, 4)))

        p1 = provider.write_bronze(df, date(2026, 5, 4))
        p2 = provider.write_bronze(df, date(2026, 5, 4))
        assert p1 == p2
        assert p1.exists()


# ---------------------------------------------------------------------------
# hkma monetary base
# ---------------------------------------------------------------------------

HKMA_FIXTURE = {
    "header": {"success": True, "err_code": "0000", "err_msg": "No error found"},
    "result": {
        "datasize": 3,
        "records": [
            {
                "end_of_date": "2026-04-29",
                "cert_of_indebt": 659305,
                "gov_notes_coins_circulation": 13284,
                "aggr_balance_bf_disc_win": 53862,
                "aggr_balance_af_disc_win": 53862,
                "outstanding_efbn": 1345858,
                "ow_lb_bf_disc_win": 1174245,
                "ow_lb_af_disc_win": 1174245,
                "mb_bf_disc_win_total": 2072309,
            },
            {
                "end_of_date": "2026-04-30",
                "cert_of_indebt": 659105,
                "gov_notes_coins_circulation": 13284,
                "aggr_balance_bf_disc_win": 53862,
                "aggr_balance_af_disc_win": 53862,
                "outstanding_efbn": 1345858,
                "ow_lb_bf_disc_win": 1174245,
                "ow_lb_af_disc_win": 1174245,
                "mb_bf_disc_win_total": 2072300,
            },
            {
                "end_of_date": "2026-05-04",
                "cert_of_indebt": 655095,
                "gov_notes_coins_circulation": 13282,
                "aggr_balance_bf_disc_win": 53862,
                "aggr_balance_af_disc_win": 53862,
                "outstanding_efbn": 1346167,
                "ow_lb_bf_disc_win": 1173974,
                "ow_lb_af_disc_win": 1173974,
                "mb_bf_disc_win_total": 2068406,
            },
        ],
    },
}


class TestHkmaMonetaryBase:
    def test_parses_official_monetary_base_api(self, tmp_data_dir):
        with patch("finsynapse.providers.hkma.requests_session") as mock_session:
            mock_session.return_value.get.return_value = _mock_response(json_data=HKMA_FIXTURE)
            provider = HkmaMonetaryBaseProvider()
            df = provider.fetch(FetchRange(start=date(2026, 4, 30), end=date(2026, 5, 4)))

        assert set(df.columns) == {"date", "indicator", "value", "source_symbol"}
        assert set(df["indicator"]) == {"hk_aggregate_balance", "hk_monetary_base"}
        assert len(df) == 4
        assert df["value"].notna().all()

    def test_hkma_api_error_raises(self, tmp_data_dir):
        error_payload = {"header": {"success": False, "err_code": "E00001", "err_msg": "API not found"}}
        with patch("finsynapse.providers.hkma.requests_session") as mock_session:
            mock_session.return_value.get.return_value = _mock_response(json_data=error_payload)
            provider = HkmaMonetaryBaseProvider()
            with pytest.raises(RuntimeError, match="HKMA API error"):
                provider.fetch(FetchRange(start=date(2026, 4, 30), end=date(2026, 5, 4)))

    def test_bronze_write_idempotent(self, tmp_data_dir):
        with patch("finsynapse.providers.hkma.requests_session") as mock_session:
            mock_session.return_value.get.return_value = _mock_response(json_data=HKMA_FIXTURE)
            provider = HkmaMonetaryBaseProvider()
            df = provider.fetch(FetchRange(start=date(2026, 4, 30), end=date(2026, 5, 4)))
        p1 = provider.write_bronze(df, date(2026, 5, 4))
        p2 = provider.write_bronze(df, date(2026, 5, 4))
        assert p1 == p2
        assert p1.exists()


# ---------------------------------------------------------------------------
# HSI Monthly Roundup valuation
# ---------------------------------------------------------------------------


class TestHsiMonthlyValuation:
    def test_fetches_official_monthly_roundup_valuation_rows(self, tmp_data_dir):
        urls = [
            "https://www.hsi.com.hk/static/uploads/contents/en/dl_centre/monthly_roundup/20241202T000000.pdf",
            "https://www.hsi.com.hk/static/uploads/contents/en/dl_centre/monthly_roundup/20250102T000000.pdf",
        ]
        valuations = [
            HsiMonthlyValuation("2024-12-02", 11.31, 3.78, urls[0]),
            HsiMonthlyValuation("2025-01-02", 11.83, 3.62, urls[1]),
        ]
        with (
            patch("finsynapse.providers.hsi_monthly_valuation.pdftotext_available", return_value=True),
            patch("finsynapse.providers.hsi_monthly_valuation.discover_hsi_monthly_roundup_urls", return_value=urls),
            patch("finsynapse.providers.hsi_monthly_valuation.fetch_hsi_monthly_roundup_valuation") as fetch_one,
        ):
            fetch_one.side_effect = valuations
            provider = HsiMonthlyValuationProvider()
            df = provider.fetch(FetchRange(start=date(2024, 12, 1), end=date(2025, 1, 31)))

        assert set(df.columns) == {"date", "indicator", "value", "source_symbol"}
        assert set(df["indicator"]) == {"hk_hsi_pe", "hk_hsi_dividend_yield"}
        assert len(df) == 4
        assert df[df["indicator"] == "hk_hsi_pe"]["value"].tolist() == [11.31, 11.83]
        assert df[df["indicator"] == "hk_hsi_dividend_yield"]["value"].tolist() == [3.78, 3.62]

    def test_bronze_write_idempotent(self, tmp_data_dir):
        df = pd.DataFrame(
            {
                "date": [date(2025, 1, 2)],
                "indicator": ["hk_hsi_pe"],
                "value": [11.83],
                "source_symbol": ["20250102T000000.pdf/PE"],
            }
        )
        provider = HsiMonthlyValuationProvider()
        p1 = provider.write_bronze(df, date(2025, 1, 2))
        p2 = provider.write_bronze(df, date(2025, 1, 2))
        assert p1 == p2
        assert p1.exists()


# ---------------------------------------------------------------------------
# yfinance_hk (EWH TTM yield)
# ---------------------------------------------------------------------------


def _mock_ewh_frame():
    import numpy as np

    idx = pd.date_range("2025-01-02", "2026-04-15", freq="B")
    closes = pd.Series(18.0 + np.sin(np.arange(len(idx)) * 0.01), index=idx)
    divs = pd.Series([0.12 if i % 60 == 0 else 0.0 for i in range(len(idx))], index=idx)
    raw = pd.DataFrame({"Close": closes, "Dividends": divs})
    raw.columns = pd.MultiIndex.from_tuples([("Close", "EWH"), ("Dividends", "EWH")])
    return raw


class TestYFinanceHk:
    def test_computes_ttm_dividend_yield(self, tmp_data_dir):
        raw = _mock_ewh_frame()
        with patch("finsynapse.providers.yfinance_hk.yf.download", return_value=raw):
            provider = YFinanceHkValuationProvider()
            df = provider.fetch(FetchRange(start=date(2026, 4, 1), end=date(2026, 4, 15)))
        assert set(df.columns) == {"date", "indicator", "value", "source_symbol"}
        assert len(df) > 0
        assert (df["indicator"] == "hk_ewh_yield_ttm").all()
        assert df["value"].notna().all()
        assert (df["value"] > 0).all()

    def test_bronze_write_idempotent(self, tmp_data_dir):
        raw = _mock_ewh_frame()
        with patch("finsynapse.providers.yfinance_hk.yf.download", return_value=raw):
            provider = YFinanceHkValuationProvider()
            df = provider.fetch(FetchRange(start=date(2026, 4, 1), end=date(2026, 4, 15)))
        p1 = provider.write_bronze(df, date(2026, 4, 15))
        p2 = provider.write_bronze(df, date(2026, 4, 15))
        assert p1 == p2
        assert p1.exists()

    def test_empty_response_raises(self, tmp_data_dir):
        with patch("finsynapse.providers.yfinance_hk.yf.download", return_value=pd.DataFrame()):
            provider = YFinanceHkValuationProvider()
            with pytest.raises(RuntimeError):
                provider.fetch(FetchRange(start=date(2026, 4, 1), end=date(2026, 4, 15)))


# ---------------------------------------------------------------------------
# retry
# ---------------------------------------------------------------------------


class TestRetry:
    def test_session_is_created_with_retry_adapter(self):
        from finsynapse.providers.retry import requests_session

        session = requests_session()
        assert session is not None
        adapters = session.adapters
        assert "https://" in adapters

    def test_session_is_cached(self):
        from finsynapse.providers.retry import requests_session

        s1 = requests_session()
        s2 = requests_session()
        assert s1 is s2

    def test_session_only_retries_idempotent_methods(self):
        from finsynapse.providers.retry import requests_session

        session = requests_session()
        adapter = session.get_adapter("https://example.com")
        allowed = adapter.max_retries.allowed_methods
        assert "GET" in allowed
        assert "POST" not in allowed
