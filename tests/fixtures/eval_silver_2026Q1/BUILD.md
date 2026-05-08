# Eval Silver Fixture 2026Q1

- **Created**: 2026-05-07
- **Source commit**: `4bbbb1b`
- **Source data**: `data/silver` baseline plus collected-only official bronze overlay: FRED `2026-05-08`, Treasury yield curve `2026-05-07`, Treasury DTS `2026-05-07`, HKMA monetary base `2026-05-07`; academic-public overlay: Yale/Shiller `2026-05-08`
- **Date window**: 2010-01-01 → 2024-12-31 (~15 years)
- **Manifest**: `MANIFEST.json` stores file hashes, row counts, date ranges, indicator lists, pivot coverage, and pivot×indicator required-window coverage
- **Manifest command**: `uv run python scripts/build_eval_fixture_manifest.py --verify`
- **Manifest test**: `uv run pytest tests/test_eval_fixture_manifest.py -q`

## Coverage

Covers all 25 historical pivots in `scripts/backtest_pivots.yaml`:
- US: 2011-10-03 through 2024-12-31 (9 pivots)
- CN: 2015-06-12 through 2024-09-23 (8 pivots)
- HK: 2015-04-27 through 2024-10-10 (8 pivots)

Weighted indicator required-window coverage at those pivots:
- Overall: 184/218 checks have the required percentile window populated
- US: 76/90; CN: 72/80; HK: 36/48
- Missing checks are listed in `MANIFEST.json → indicator_pivot_coverage.missing_required_percentiles`

Collected-only official and academic-public overlays now included in `macro_daily.parquet` and
`percentile_daily.parquet` without changing `temperature_daily.parquet`:
- HKMA: `hk_aggregate_balance`, `hk_monetary_base`
- U.S. Treasury / FRED: `us3m_yield`, `us_t10y3m`, `us_baa10y_spread`, `us_on_rrp`, `us_reserve_balances`, `us_effr`, `us_sofr`
- U.S. Treasury DTS: `us_tga_balance`, `us_tga_deposits`, `us_tga_withdrawals`
- Yale/Shiller: `us_shiller_real_price`, `us_shiller_real_dividend`, `us_shiller_real_earnings`, `us_cape_shiller`, `us_tr_cape_shiller`

Candidate comparison against the previous fixture showed +32,845 macro rows,
+12 indicators, unchanged weighted pivot coverage (184/218), unchanged gate
metrics, and no pivot changes.

Adding the Yale/Shiller valuation-base overlay on 2026-05-08 added +900 macro
rows and +19,565 percentile rows for five collected-only indicators
(`us_shiller_real_price`, `us_shiller_real_dividend`,
`us_shiller_real_earnings`, `us_cape_shiller`, `us_tr_cape_shiller`). Weighted
pivot coverage stayed 184/218, gate metrics were unchanged, and no pivot
classifications changed.

## Tested But Not Promoted

- **2026-05-08 yfinance/FRED warmup candidate**: extending yfinance/FRED lookback
  to 9,000 days improved US required-window coverage from 76/90 to 83/90 and
  reduced total missing checks from 34 to 27. It was not promoted because
  `mean_reversion_strength.3m.hk` fell from 0.1470 to 0.1154 and failed the
  champion gate; the failing HK pivot was driven by `us10y_real_yield` liquidity
  percentile changes at the 2016 HK crash pivot.
- **2026-05-08 warmup + HK VHSI candidate**: adding the source-ready VHSI history
  improved total required-window coverage from 184/218 to 199/218, but
  `pivot_directional_rate` fell from 0.9200 to 0.8800 and failed the block gate.
  The 2024-10-10 HK policy-pivot surge flipped from mid to cold, so VHSI needs a
  weight/pivot policy review before fixture promotion.

Key regime coverage: 2018 trade war, 2020 COVID, 2022 Fed hiking.

## Why Silver Not Bronze

Silver is the stable intermediate layer (`normalize → percentile`). Bronze upstream
interfaces (FRED rolling windows, AkShare discontinued endpoints) can drift over time.
Using silver as fixture prevents upstream drift from polluting eval baselines.

## Files

| File | Description |
|------|-------------|
| `macro_daily.parquet` | Long-format macro indicators (index prices for forward returns) |
| `percentile_daily.parquet` | Rolling percentile ranks (pct_1y/5y/10y) |
| `temperature_daily.parquet` | Per-market overall + sub temperatures |
| `MANIFEST.json` | Machine-readable fixture audit manifest |

## Regeneration

To regenerate with updated data:
1. Run a full daily pipeline to produce fresh `data/silver/` files
2. Slice `macro_daily.parquet`, `percentile_daily.parquet`, and `temperature_daily.parquet` to `2010-01-01..2024-12-31`
3. For a collected-only overlay, append only non-weighted indicators to `macro_daily.parquet`, append their own percentile rows to `percentile_daily.parquet`, and preserve `temperature_daily.parquet` unless weights change
4. Compare against the previous fixture: `uv run python scripts/compare_eval_fixtures.py --candidate <candidate-dir>`
5. Recompute `MANIFEST.json`: `uv run python scripts/build_eval_fixture_manifest.py --write --created YYYY-MM-DD --source-commit <sha> --source-data '<description>'`
6. Update this BUILD.md with the new source data and comparison result
7. Run `uv run python scripts/build_eval_fixture_manifest.py --verify`
8. Run `uv run pytest tests/test_eval_fixture_manifest.py -q`
