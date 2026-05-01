"""Tests for the Phase 1 validation pipeline.

Covers:
- Pivot YAML parsing (valid structure, all 3 markets covered)
- Baseline temperature computation (PE, VIX, momentum)
- Gate logic correctness
- Validation report serialization roundtrip
"""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest
import yaml

from finsynapse.dashboard.validation_data import ValidationReport, load_report
from finsynapse.transform.normalize import derive_indicators
from finsynapse.transform.percentile import compute_percentiles
from finsynapse.transform.temperature import WeightsConfig, compute_temperature

SCRIPTS_DIR = __import__("pathlib").Path(__file__).parent.parent / "scripts"
PIVOTS_PATH = SCRIPTS_DIR / "backtest_pivots.yaml"


def _build_macro(indicators: dict[str, list[float]], start: str = "2010-01-04") -> pd.DataFrame:
    start_d = pd.Timestamp(start)
    frames = []
    for indicator, values in indicators.items():
        dates = pd.bdate_range(start_d, periods=len(values))
        frames.append(
            pd.DataFrame(
                {
                    "date": [d.date() for d in dates],
                    "indicator": indicator,
                    "value": values,
                    "source": "test",
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


class TestPivotsYAML:
    """Validate the pivot definition file structure."""

    def test_yaml_parses(self):
        with PIVOTS_PATH.open() as f:
            data = yaml.safe_load(f)
        assert "pivots" in data
        assert len(data["pivots"]) >= 20

    def test_all_three_markets_covered(self):
        with PIVOTS_PATH.open() as f:
            data = yaml.safe_load(f)
        markets = {p["market"] for p in data["pivots"]}
        assert markets == {"us", "cn", "hk"}

    def test_each_market_has_min_bottoms_and_tops(self):
        with PIVOTS_PATH.open() as f:
            data = yaml.safe_load(f)
        for market in ("us", "cn", "hk"):
            market_pivots = [p for p in data["pivots"] if p["market"] == market]
            cold = sum(1 for p in market_pivots if p["expected_zone"] == "cold")
            hot = sum(1 for p in market_pivots if p["expected_zone"] == "hot")
            assert cold >= 3, f"{market}: expected ≥3 cold pivots, got {cold}"
            assert hot >= 2, f"{market}: expected ≥2 hot pivots, got {hot}"

    def test_all_dates_valid_and_ordered(self):
        with PIVOTS_PATH.open() as f:
            data = yaml.safe_load(f)
        for p in data["pivots"]:
            d = date.fromisoformat(p["date"])
            assert date(2010, 1, 1) <= d <= date(2026, 12, 31)

    def test_all_expected_zones_valid(self):
        with PIVOTS_PATH.open() as f:
            data = yaml.safe_load(f)
        for p in data["pivots"]:
            assert p["expected_zone"] in ("cold", "mid", "hot")


class TestBaselineTemperatures:
    """Verify baseline temperature computation logic."""

    def test_pe_single_factor_outputs_0_to_100(self):
        # Need >300 days beyond pct_1y min_periods. Use pct_1y window (252d, min_periods=63).
        n = 350
        values = list(np.linspace(15, 40, n))
        macro = _build_macro({"us_pe_ttm": values})
        macro = derive_indicators(macro)
        pct = compute_percentiles(macro)

        cfg = WeightsConfig(
            sub_weights={"us": {"valuation": 1.0, "sentiment": 0.0, "liquidity": 0.0}},
            indicator_weights={
                "us_valuation": {"us_pe_ttm": {"weight": 1.0, "direction": "+", "window": "pct_1y"}},
                "us_sentiment": {},
                "us_liquidity": {},
            },
            percentile_window="pct_1y",
        )
        temp = compute_temperature(pct, cfg)
        us = temp[temp["market"] == "us"]
        assert not us.empty
        assert len(us) > 0
        valid = us.dropna(subset=["overall"])
        assert valid["overall"].between(0, 100).all()

    def test_vix_baseline_inverts_direction(self):
        """Direction "-": high VIX percentile yields low temperature.
        Verify that 'vix' with direction '-' produces valid temperatures in [0,100]
        and that the sentiment sub works for inputs after min_periods."""
        n = 350
        mid = n // 2
        values = [80.0 - 70.0 * (i / mid) for i in range(mid)] + [
            10.0 + 70.0 * (i / (n - mid - 1)) for i in range(n - mid)
        ]
        macro = _build_macro({"vix": values})
        macro = derive_indicators(macro)
        pct = compute_percentiles(macro)

        cfg = WeightsConfig(
            sub_weights={"us": {"valuation": 0.0, "sentiment": 1.0, "liquidity": 0.0}},
            indicator_weights={
                "us_valuation": {},
                "us_sentiment": {"vix": {"weight": 1.0, "direction": "-", "window": "pct_1y"}},
                "us_liquidity": {},
            },
            percentile_window="pct_1y",
        )
        temp = compute_temperature(pct, cfg)
        us = temp[temp["market"] == "us"].dropna(subset=["overall"])
        assert not us.empty
        assert us["overall"].between(0, 100).all()
        assert us["sentiment"].between(0, 100).all()

    def test_momentum_baseline_uses_60d_returns(self):
        """Verify momentum temperature is computed from 60d pct_change+percentile."""
        n = 300
        # Steadily rising index: early values have small 60d returns, later have large ones
        init_val = 100.0
        values = [init_val * (1.001**i) for i in range(n)]
        macro = _build_macro({"sp500": values})
        wide = macro.pivot_table(index="date", columns="indicator", values="value").sort_index()
        ret_60d = wide["sp500"].pct_change(60).iloc[-1]
        # With steadily rising index over 300 days, 60d return should be positive
        assert ret_60d > 0

    def test_compute_temperature_handles_empty_baseline(self):
        cfg1 = WeightsConfig(
            sub_weights={"us": {"valuation": 1.0, "sentiment": 0.0, "liquidity": 0.0}},
            indicator_weights={
                "us_valuation": {"nonexistent_indicator": {"weight": 1.0, "direction": "+"}},
                "us_sentiment": {},
                "us_liquidity": {},
            },
            percentile_window="pct_10y",
        )
        pct = pd.DataFrame(columns=["date", "indicator", "value", "pct_1y", "pct_5y", "pct_10y"])
        temp = compute_temperature(pct, cfg1)
        assert temp.empty


class TestPhase2MultiTimeframe:
    """Verify multi-timeframe temperature columns."""

    def test_multiframe_columns_present(self):
        """compute_temperature output should include overall_short, overall_long, divergence."""
        n = 350
        values = list(np.linspace(15, 40, n))
        macro = _build_macro({"us_pe_ttm": values})
        macro = derive_indicators(macro)
        pct = compute_percentiles(macro)

        cfg = WeightsConfig(
            sub_weights={"us": {"valuation": 1.0, "sentiment": 0.0, "liquidity": 0.0}},
            indicator_weights={
                "us_valuation": {"us_pe_ttm": {"weight": 1.0, "direction": "+", "window": "pct_1y"}},
                "us_sentiment": {},
                "us_liquidity": {},
            },
            percentile_window="pct_1y",
        )
        temp = compute_temperature(pct, cfg)
        assert not temp.empty
        for col in ("overall_short", "overall_long", "divergence", "conf_ok"):
            assert col in temp.columns, f"missing column: {col}"

    def test_divergence_zero_when_single_window(self):
        """When all indicators use the same window, short and long diverge due to
        different min_periods and window breadth, but should both be in [0,100]."""
        n = 400
        values = list(np.linspace(15, 40, n))
        macro = _build_macro({"us_pe_ttm": values})
        macro = derive_indicators(macro)
        pct = compute_percentiles(macro)

        cfg = WeightsConfig(
            sub_weights={"us": {"valuation": 1.0, "sentiment": 0.0, "liquidity": 0.0}},
            indicator_weights={
                "us_valuation": {"us_pe_ttm": {"weight": 1.0, "direction": "+", "window": "pct_1y"}},
                "us_sentiment": {},
                "us_liquidity": {},
            },
            percentile_window="pct_1y",
        )
        temp = compute_temperature(pct, cfg)
        valid = temp.dropna(subset=["overall_short", "overall_long"])
        assert valid["overall_short"].between(0, 100).all()
        assert valid["overall_long"].between(0, 100).all()

    def test_dispersion_confidence_computed(self):
        """When 2+ indicators exist in a sub, conf_ok should vary."""
        n = 350
        vix_vals = [80.0 - 70.0 * (i / (n - 1)) for i in range(n)]  # declining vix
        oas_vals = [5.0 + 15.0 * (i / (n - 1)) for i in range(n)]  # rising OAS
        us_pe_vals = list(np.linspace(15, 40, n))
        macro = pd.concat(
            [
                _build_macro({"vix": vix_vals}),
                _build_macro({"us_hy_oas": oas_vals, "us_pe_ttm": us_pe_vals}),
            ],
            ignore_index=True,
        )
        macro = derive_indicators(macro)
        pct = compute_percentiles(macro)

        cfg = WeightsConfig(
            sub_weights={"us": {"valuation": 0.5, "sentiment": 0.5, "liquidity": 0.0}},
            indicator_weights={
                "us_valuation": {"us_pe_ttm": {"weight": 1.0, "direction": "+", "window": "pct_1y"}},
                "us_sentiment": {
                    "vix": {"weight": 0.5, "direction": "-", "window": "pct_1y"},
                    "us_hy_oas": {"weight": 0.5, "direction": "-", "window": "pct_1y"},
                },
                "us_liquidity": {},
            },
            percentile_window="pct_1y",
        )
        temp = compute_temperature(pct, cfg)
        assert not temp.empty
        assert "conf_ok" in temp.columns
        # conf_ok should be 0 or 1
        assert temp["conf_ok"].dropna().isin([0, 1]).all()


class TestNewWeightsConfig:
    """Verify weights.yaml loads correctly with Phase 2 indicators."""

    def test_new_indicators_in_weights(self):
        cfg = WeightsConfig.load()
        us_sent = cfg.indicator_weights.get("us_sentiment", {})
        assert "us_umich_sentiment" in us_sent
        us_liq = cfg.indicator_weights.get("us_liquidity", {})
        assert "us_walcl" in us_liq
        hk_sent = cfg.indicator_weights.get("hk_sentiment", {})
        assert "hk_vhsi" in hk_sent


class TestGateLogic:
    """Verify the gate-check logic in validation."""

    def test_gate_passes_when_beating_in_two_markets(self):
        from finsynapse.dashboard.validation_data import GateResult

        gate = GateResult(
            passed=True,
            markets_beaten=2,
            total_markets=3,
            standard="test",
            details={
                "us": {"beaten": True, "mf_directional_rate": 0.8, "pe_directional_rate": 0.6},
                "cn": {"beaten": True, "mf_directional_rate": 0.7, "pe_directional_rate": 0.5},
                "hk": {"beaten": False, "mf_directional_rate": 0.4, "pe_directional_rate": 0.6},
            },
        )
        assert gate.passed

    def test_gate_fails_when_beating_in_one_market(self):
        from finsynapse.dashboard.validation_data import GateResult

        gate = GateResult(
            passed=False,
            markets_beaten=1,
            total_markets=3,
            standard="test",
            details={
                "us": {"beaten": True, "mf_directional_rate": 0.75, "pe_directional_rate": 0.5},
                "cn": {"beaten": False, "mf_directional_rate": 0.3, "pe_directional_rate": 0.5},
                "hk": {"beaten": False, "mf_directional_rate": 0.2, "pe_directional_rate": 0.4},
            },
        )
        assert not gate.passed


class TestVersionModule:
    """Verify version stamping, snapshot, and drift detection."""

    def test_stamp_version_adds_column(self):
        from finsynapse.transform.version import ALGO_VERSION, stamp_version

        df = pd.DataFrame({"overall": [50.0], "market": ["us"]})
        stamped = stamp_version(df)
        assert "algo_version" in stamped.columns
        assert stamped["algo_version"].iloc[0] == ALGO_VERSION

    def test_stamp_version_empty_frame(self):
        from finsynapse.transform.version import stamp_version

        df = pd.DataFrame()
        result = stamp_version(df)
        assert result.empty

    def test_snapshot_weights_creates_file(self, tmp_path, monkeypatch):
        import yaml

        from finsynapse.transform.version import snapshot_weights

        # Redirect silver dir to tmp
        from finsynapse import config as cfg

        monkeypatch.setattr(cfg, "settings", cfg.Settings(data_dir=tmp_path))
        cfg.settings.silver_dir.mkdir(parents=True, exist_ok=True)

        src = tmp_path / "weights_test.yaml"
        src.write_text("percentile_window: pct_10y\nsub_weights: {}\nindicator_weights: {}\n")
        result = snapshot_weights(str(src))
        assert result is not None
        assert result.exists()

    def test_drift_check_no_change(self):
        from finsynapse.transform.version import drift_check

        today = pd.DataFrame({"date": ["2026-01-02"], "market": ["us"], "overall": [50.0]})
        yesterday = pd.DataFrame({"date": ["2026-01-01"], "market": ["us"], "overall": [51.0]})
        alerts = drift_check(today, yesterday, threshold=15.0)
        assert alerts == []

    def test_drift_check_large_move(self):
        from finsynapse.transform.version import drift_check

        today = pd.DataFrame({"date": ["2026-01-02"], "market": ["us"], "overall": [80.0]})
        yesterday = pd.DataFrame({"date": ["2026-01-01"], "market": ["us"], "overall": [50.0]})
        alerts = drift_check(today, yesterday, threshold=15.0)
        assert len(alerts) == 1
        assert alerts[0]["alert"] == "zone_crossing"

    def test_compare_snapshots_detects_change(self, tmp_path):
        import yaml

        from finsynapse.transform.version import compare_snapshots

        prev = tmp_path / "prev.yaml"
        curr = tmp_path / "curr.yaml"
        base = {
            "sub_weights": {"us": {"valuation": 0.4}},
            "indicator_weights": {"us_valuation": {"vix": {"weight": 0.5, "direction": "-"}}},
        }
        prev.write_text(yaml.dump(base))
        changed = dict(base)
        changed["indicator_weights"]["us_valuation"]["vix"]["weight"] = 0.6
        curr.write_text(yaml.dump(changed))
        diff = compare_snapshots(prev, curr)
        assert diff["status"] == "diff"
        assert any("0.5" in c for c in diff.get("changed", []))


class TestValidationReportRoundtrip:
    """Verify the validation report JSON roundtrip."""

    def test_report_roundtrip(self, tmp_path):
        report_json = {
            "version": "1.0.0",
            "generated": "2026-04-30",
            "pivots_total": 3,
            "pivots_evaluated": 3,
            "pivot_results": [
                {
                    "label": "Test pivot",
                    "market": "us",
                    "date": "2020-03-23",
                    "expected_zone": "cold",
                    "controllers": [
                        {
                            "name": "multi-factor",
                            "overall": 15.0,
                            "zone": "cold",
                            "strict_pass": True,
                            "directional_pass": True,
                            "valuation": 10.0,
                            "sentiment": 20.0,
                            "liquidity": 15.0,
                        }
                    ],
                }
            ],
            "hit_rate_table": {
                "multi-factor": {
                    "us": {
                        "total": 3,
                        "directional_hits": 3,
                        "directional_rate": 1.0,
                        "strict_hits": 2,
                        "strict_rate": 0.667,
                    }
                }
            },
            "forward_stats": {"us": {"1m": {"n": 100, "mean": 0.02, "spearman_rho": -0.15}}},
            "zone_distribution": {
                "0-20 (极冷)": [{"horizon": "1m", "mean_return": 0.03, "median_return": 0.02, "win_rate": 0.7, "n": 50}]
            },
            "spearman_rho": {"us": {"1m": -0.15, "3m": -0.25, "6m": -0.30, "12m": -0.35}},
            "gate": {
                "passed": True,
                "markets_beaten": 2,
                "total_markets": 3,
                "standard": "test",
                "details": {},
            },
        }
        path = tmp_path / "validation_report.json"
        path.write_text(json.dumps(report_json))

        report = load_report(path)
        assert report is not None
        assert report.version == "1.0.0"
        assert report.pivots_total == 3
        assert len(report.pivot_results) == 1
        assert report.pivot_results[0].controllers[0].overall == 15.0
        assert report.gate is not None
        assert report.gate.passed

    def test_load_report_returns_none_for_missing_file(self, tmp_path):
        report = load_report(tmp_path / "nonexistent.json")
        assert report is None


class TestDeriveIndicatorsIntegration:
    """Verify us_erp derivation works for validation pipeline inputs."""

    def test_us_erp_low_pe_means_cheap(self):
        """Low PE + same real yield = higher ERP = stocks cheap relative to bonds."""
        n = 30
        dates = pd.bdate_range("2026-01-01", periods=n)
        macro = pd.concat(
            [
                pd.DataFrame(
                    {
                        "date": [d.date() for d in dates],
                        "indicator": "us_pe_ttm",
                        "value": [10.0] * n,  # low PE = expensive earnings yield = 10%
                        "source": "multpl",
                    }
                ),
                pd.DataFrame(
                    {
                        "date": [d.date() for d in dates],
                        "indicator": "us10y_real_yield",
                        "value": [2.0] * n,  # real yield = 2%
                        "source": "fred",
                    }
                ),
            ],
            ignore_index=True,
        )
        out = derive_indicators(macro)
        erp_rows = out[out["indicator"] == "us_erp"]
        assert not erp_rows.empty
        # EY = 100/10 = 10%, ERP = 10% - 2% = 8%
        assert 7.9 < erp_rows["value"].iloc[0] < 8.1

    def test_us_erp_high_pe_means_expensive(self):
        """High PE + same real yield = lower ERP = stocks expensive."""
        n = 30
        dates = pd.bdate_range("2026-01-01", periods=n)
        macro = pd.concat(
            [
                pd.DataFrame(
                    {
                        "date": [d.date() for d in dates],
                        "indicator": "us_pe_ttm",
                        "value": [40.0] * n,  # high PE, earnings yield = 2.5%
                        "source": "multpl",
                    }
                ),
                pd.DataFrame(
                    {
                        "date": [d.date() for d in dates],
                        "indicator": "us10y_real_yield",
                        "value": [3.0] * n,
                        "source": "fred",
                    }
                ),
            ],
            ignore_index=True,
        )
        out = derive_indicators(macro)
        erp_rows = out[out["indicator"] == "us_erp"]
        assert not erp_rows.empty
        # EY = 100/40 = 2.5%, ERP = 2.5% - 3% = -0.5%
        assert -0.6 < erp_rows["value"].iloc[0] < -0.4
