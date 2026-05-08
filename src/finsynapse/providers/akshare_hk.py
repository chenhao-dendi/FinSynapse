"""AkShare HK macro provider — HKD funding conditions and volatility.

Validated by scripts/probe_phase_b.py 2026-04-29:
    - macro_china_hk_market_info()  — HIBOR all tenors daily (2,236 rows from 2017-03)
Validated by live probe 2026-05-07:
    - stock_hk_index_daily_em(symbol="VHSI") — VHSI daily history from 2001-01

Why HIBOR (vs just borrowing US real yield + DXY for HK liquidity):
    HK pegs HKD to USD (7.75-7.85 corridor) so US conditions matter, BUT the
    HKMA defends the peg by absorbing/releasing HKD liquidity, which moves
    HIBOR independently of Fed Funds. When carry trades unwind or capital
    flees, HIBOR-1M can spike 100-200bp in days while DXY barely budges (e.g.
    Sep 2018, Mar 2020, Aug 2022). Borrowing only US gauges misses this.
"""

from __future__ import annotations

from datetime import date

import akshare as ak
import pandas as pd

from finsynapse.providers.akshare_cn import _pick_col
from finsynapse.providers.base import FetchRange, Provider


def _hibor_all() -> pd.DataFrame:
    """HIBOR all tenors daily fixings (wide format, columns like '1M-定价').
    Intentionally NOT lru_cache'd — AkShare publishes daily; a long-running
    process must re-fetch to pick up new rows."""
    return ak.macro_china_hk_market_info()


def _vhsi_daily() -> pd.DataFrame:
    """HSI Volatility Index daily OHLC.

    AkShare's Eastmoney endpoint has longer VHSI history than Sina and
    yfinance `^VHSI` currently returns quote-not-found. We keep the canonical
    indicator as `hk_vhsi` so the temperature layer does not change.
    """
    return ak.stock_hk_index_daily_em(symbol="VHSI")


def _slice_dates(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df[(df["date"] >= start) & (df["date"] <= end)]


class AkShareHkProvider(Provider):
    name = "akshare_hk"
    layer = "macro"

    def fetch(self, fetch_range: FetchRange) -> pd.DataFrame:
        hibor = _hibor_all().copy()
        hibor["日期"] = pd.to_datetime(hibor["日期"]).dt.date
        # 1M tenor is the standard HIBOR reference for funding cost. Shorter
        # tenors (O/N, 1W) are noisier; longer (3M, 6M) lag too much.
        # AkShare column rename defense — same pattern as akshare_cn SHIBOR.
        hibor_1m_col = _pick_col(hibor, ("1M-定价", "1M", "1月-定价"), "macro_china_hk_market_info")
        hibor_long = pd.DataFrame(
            {
                "date": hibor["日期"],
                "value": pd.to_numeric(hibor[hibor_1m_col], errors="coerce"),
                "indicator": "hk_hibor_1m",
                "source_symbol": f"macro_china_hk_market_info/{hibor_1m_col}",
            }
        ).dropna(subset=["value"])
        vhsi = _vhsi_daily().copy()
        close_col = _pick_col(vhsi, ("latest", "close", "收盘", "最新价"), "stock_hk_index_daily_em/VHSI")
        vhsi_long = pd.DataFrame(
            {
                "date": pd.to_datetime(vhsi["date"]).dt.date,
                "value": pd.to_numeric(vhsi[close_col], errors="coerce"),
                "indicator": "hk_vhsi",
                "source_symbol": f"stock_hk_index_daily_em/VHSI/{close_col}",
            }
        ).dropna(subset=["value"])
        out = pd.concat(
            [
                _slice_dates(hibor_long, fetch_range.start, fetch_range.end),
                _slice_dates(vhsi_long, fetch_range.start, fetch_range.end),
            ],
            ignore_index=True,
        )
        if out.empty:
            raise RuntimeError(f"akshare_hk returned 0 rows in range {fetch_range.start}..{fetch_range.end}")
        return out.sort_values(["indicator", "date"]).reset_index(drop=True)


def run(fetch_range: FetchRange, fetch_date: date | None = None) -> tuple[pd.DataFrame, str]:
    provider = AkShareHkProvider()
    df = provider.fetch(fetch_range)
    path = provider.write_bronze(df, fetch_date or date.today())
    return df, str(path)
