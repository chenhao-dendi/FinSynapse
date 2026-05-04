from __future__ import annotations

import gzip
import json
from pathlib import Path

import pandas as pd
import pytest

from finsynapse.dashboard.api import API_SCHEMA_VERSION, _safe_float, build_manifest, write_all
from finsynapse.dashboard.data import DashboardData


def _empty_dashboard_data(tmp_path: Path) -> DashboardData:
    return DashboardData(
        temperature=pd.DataFrame(),
        macro=pd.DataFrame(),
        percentile=pd.DataFrame(),
        divergence=pd.DataFrame(),
        health=pd.DataFrame(),
        silver_dir=tmp_path,
    )


def _sample_dashboard_data(tmp_path: Path) -> DashboardData:
    temp = pd.DataFrame(
        [
            {
                "date": "2026-04-30",
                "market": "us",
                "overall": 75.2,
                "valuation": 80.0,
                "sentiment": 70.0,
                "liquidity": 65.0,
                "overall_change_1w": 1.2,
                "valuation_contribution_1w": 0.4,
                "sentiment_contribution_1w": 0.5,
                "liquidity_contribution_1w": 0.3,
                "subtemp_completeness": 3,
                "conf_ok": 1,
                "is_complete": True,
                "data_quality": "ok",
            },
            {
                "date": "2026-04-30",
                "market": "cn",
                "overall": 55.0,
                "valuation": 60.0,
                "sentiment": 50.0,
                "liquidity": 55.0,
                "overall_change_1w": -0.5,
                "valuation_contribution_1w": -0.2,
                "sentiment_contribution_1w": -0.1,
                "liquidity_contribution_1w": -0.2,
                "subtemp_completeness": 3,
                "conf_ok": 0,
                "is_complete": True,
                "data_quality": "ok",
            },
        ]
    )
    pct = pd.DataFrame(
        [
            {"date": "2026-04-30", "indicator": "vix", "value": 18.5, "pct_5y": 45.0, "pct_10y": 50.0},
            {"date": "2026-04-30", "indicator": "us_pe_ttm", "value": 28.0, "pct_5y": 80.0, "pct_10y": 85.0},
            {"date": "2026-04-29", "indicator": "cn_m2_yoy", "value": 8.1, "pct_5y": 35.0, "pct_10y": 40.0},
        ]
    )
    macro = pd.DataFrame(
        [
            {"date": "2026-04-30", "indicator": "vix", "value": 18.5, "source": "yfinance"},
            {"date": "2026-04-30", "indicator": "us_pe_ttm", "value": 28.0, "source": "multpl"},
            {"date": "2026-04-29", "indicator": "cn_m2_yoy", "value": 8.1, "source": "akshare"},
        ]
    )
    div = pd.DataFrame(
        [
            {
                "date": "2026-04-30",
                "pair_name": "sp500_vix",
                "is_divergent": True,
                "strength": 0.55,
                "description": "SP\u2191+VIX\u2191 divergence",
                "a_change": 0.02,
                "b_change": 0.10,
            }
        ]
    )
    return DashboardData(
        temperature=temp,
        macro=macro,
        percentile=pct,
        divergence=div,
        health=pd.DataFrame(),
        silver_dir=tmp_path,
    )


def test_manifest_lists_endpoints_and_schema():
    manifest = build_manifest(
        asof="2026-04-30",
        endpoints=["temperature_latest.json", "indicators_latest.json"],
        generated_at_utc="2026-04-30T22:00:00Z",
        market_asof={"cn": "2026-04-29", "us": "2026-04-30"},
        latest_complete_date={"cn": "2026-04-29", "us": "2026-04-30"},
        raw_temperature_asof="2026-04-30",
    )
    assert API_SCHEMA_VERSION == "2.0.0"
    assert manifest["schema_version"] == API_SCHEMA_VERSION
    assert manifest["asof"] == "2026-04-30"
    assert manifest["generated_at_utc"] == "2026-04-30T22:00:00Z"
    assert manifest["market_asof"]["cn"] == "2026-04-29"
    assert manifest["latest_complete_date"]["us"] == "2026-04-30"
    assert manifest["raw_temperature_asof"] == "2026-04-30"
    assert "temperature_latest.json" in manifest["endpoints"]
    assert manifest["endpoints"]["temperature_latest.json"]["description"]


def test_temperature_latest_payload_structure(tmp_path: Path):
    data = _sample_dashboard_data(tmp_path)
    paths = write_all(data, tmp_path / "dist")
    payload_path = tmp_path / "dist" / "api" / "temperature_latest.json"
    assert payload_path in paths
    payload = json.loads(payload_path.read_text())
    assert payload["asof"] == "2026-04-30"
    assert payload["market_asof"] == {"cn": "2026-04-30", "hk": None, "us": "2026-04-30"}
    assert payload["latest_complete_date"] == {"cn": "2026-04-30", "hk": None, "us": "2026-04-30"}
    assert payload["raw_temperature_asof"] == "2026-04-30"
    assert payload["schema_version"]
    assert "us" in payload["markets"]
    us = payload["markets"]["us"]
    assert us["overall"] == 75.2
    assert us["sub_temperatures"]["valuation"] == 80.0
    assert us["change_1w"]["overall"] == 1.2
    assert us["change_1w"]["attribution"]["valuation"] == 0.4
    assert us["data_quality"] == "ok"
    assert us["subtemp_completeness"] == 3
    assert us["conf_ok"] == 1
    assert us["is_complete"] is True
    assert payload["markets"]["cn"]["conf_ok"] == 0


def test_temperature_latest_handles_empty_data(tmp_path: Path):
    data = _empty_dashboard_data(tmp_path)
    paths = write_all(data, tmp_path / "dist")
    assert paths == []


def test_indicators_latest_payload(tmp_path: Path):
    data = _sample_dashboard_data(tmp_path)
    write_all(data, tmp_path / "dist")
    payload = json.loads((tmp_path / "dist" / "api" / "indicators_latest.json").read_text())
    assert payload["asof"] == "2026-04-30"
    assert payload["raw_percentile_asof"] == "2026-04-30"
    by_name = {item["indicator"]: item for item in payload["indicators"]}
    assert "vix" in by_name
    assert by_name["vix"]["value"] == 18.5
    assert by_name["vix"]["percentile_5y"] == 45.0
    assert by_name["vix"]["percentile_10y"] == 50.0
    assert by_name["vix"]["last_seen"] == "2026-04-30"
    assert by_name["vix"]["days_stale"] == 0
    assert by_name["vix"]["source"] == "yfinance"
    assert by_name["cn_m2_yoy"]["last_seen"] == "2026-04-29"
    assert by_name["cn_m2_yoy"]["days_stale"] == 1
    assert by_name["cn_m2_yoy"]["source"] == "akshare"


def test_divergence_latest_payload(tmp_path: Path):
    data = _sample_dashboard_data(tmp_path)
    write_all(data, tmp_path / "dist")
    payload = json.loads((tmp_path / "dist" / "api" / "divergence_latest.json").read_text())
    assert payload["window_days"] == 90
    assert len(payload["signals"]) == 1
    sig = payload["signals"][0]
    assert sig["pair"] == "sp500_vix"
    assert sig["strength"] == 0.55
    assert sig["a_change_pct"] == 2.0
    assert sig["b_change_pct"] == 10.0


def test_temperature_history_is_gzipped_and_per_market(tmp_path: Path):
    data = _sample_dashboard_data(tmp_path)
    write_all(data, tmp_path / "dist")
    history_path = tmp_path / "dist" / "api" / "temperature_history.json.gz"
    assert history_path.exists()
    payload = json.loads(gzip.decompress(history_path.read_bytes()).decode("utf-8"))
    assert payload["schema_version"]
    assert "us" in payload["markets"]
    us_series = payload["markets"]["us"]
    assert us_series[0]["date"] == "2026-04-30"
    assert us_series[0]["overall"] == 75.2
    assert us_series[0]["valuation"] == 80.0


def test_safe_float_rejects_non_numeric_scalars():
    assert _safe_float("18.5") == 18.5
    assert _safe_float(None) is None
    with pytest.raises(TypeError):
        _safe_float({"value": 18.5})
    with pytest.raises(TypeError):
        _safe_float([18.5])
    with pytest.raises(TypeError):
        _safe_float("not-a-number")


def test_risk_bucket_boundaries():
    from finsynapse.dashboard import render_static

    assert render_static._risk_bucket(0.0099) == ("risk_weak", 1, "navy")
    assert render_static._risk_bucket(0.01) == ("risk_low", 2, "navy")
    assert render_static._risk_bucket(0.1) == ("risk_med", 3, "gold")
    assert render_static._risk_bucket(0.5) == ("risk_high", 4, "coral")


def test_render_static_writes_api_manifest(tmp_path: Path, monkeypatch):
    """Smoke test: the public render() path writes API files through render()."""
    from finsynapse.dashboard import render_static

    class FakeWeightsConfig:
        def __init__(self):
            self.sub_weights = {
                "cn": {"valuation": 0.65, "sentiment": 0.2, "liquidity": 0.15},
                "hk": {"valuation": 0.6, "sentiment": 0.25, "liquidity": 0.15},
                "us": {"valuation": 0.35, "sentiment": 0.45, "liquidity": 0.2},
            }
            self.indicator_weights = {
                "cn_valuation": {"csi300_pe_ttm": {"weight": 1.0, "direction": "+"}},
                "cn_sentiment": {"cn_a_turnover_5d": {"weight": 1.0, "direction": "+"}},
                "cn_liquidity": {"cn_m2_yoy": {"weight": 1.0, "direction": "+"}},
                "hk_valuation": {"hk_ewh_yield_ttm": {"weight": 1.0, "direction": "-"}},
                "hk_sentiment": {"cn_south_5d": {"weight": 1.0, "direction": "+"}},
                "hk_liquidity": {"hk_hibor_1m": {"weight": 1.0, "direction": "-"}},
                "us_valuation": {"us_pe_ttm": {"weight": 1.0, "direction": "+"}},
                "us_sentiment": {"vix": {"weight": 1.0, "direction": "-"}},
                "us_liquidity": {"dxy": {"weight": 1.0, "direction": "-"}},
            }

        @classmethod
        def load(cls):
            return cls()

    monkeypatch.setattr(render_static, "list_briefs", lambda: [])
    monkeypatch.setattr(render_static, "WeightsConfig", FakeWeightsConfig)

    data = _sample_dashboard_data(tmp_path)
    out_dir = tmp_path / "dist"
    render_static.render(out_dir, data=data)

    assert (out_dir / "index.html").exists()
    assert (out_dir / "en.html").exists()
    manifest = json.loads((out_dir / "api" / "manifest.json").read_text())
    assert manifest["generated_at_utc"]
    assert (out_dir / "api" / "temperature_latest.json").exists()
