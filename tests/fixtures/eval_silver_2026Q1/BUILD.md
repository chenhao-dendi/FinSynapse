# Eval Silver Fixture 2026Q1

- **Created**: 2026-05-06
- **Source commit**: `4bbbb1b`
- **Source data**: `data/silver/{macro_daily,percentile_daily,temperature_daily}.parquet`
- **Date window**: 2010-01-01 → 2024-12-31 (~15 years)
- **Slice script**: `uv run python -c "..."` (ad-hoc, see P0a-1 in eval plan)

## Coverage

Covers all 24 historical pivots in `scripts/backtest_pivots.yaml`:
- US: 2011-10-03 through 2024-12-31 (9 pivots)
- CN: 2015-06-12 through 2024-09-23 (8 pivots)
- HK: 2015-04-27 through 2024-10-10 (7 pivots, missing 2016-01-20)

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

## Regeneration

To regenerate with updated data:
1. Run a full daily pipeline to produce fresh `data/silver/` files
2. Slice the same date window with the slice script above
3. Update this BUILD.md with the new source commit
