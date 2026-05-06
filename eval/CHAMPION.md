# Champion Promotion History

> `maturity: Lv5`

| # | Date | Commit | PR | Reason | Key Delta |
|---|---|---|---|---|---|
| 0 | 2026-05-06 | `4bbbb1b` | — | Initial champion — full P0→P3 maturity pipeline on eval_silver_2026Q1 fixture | dir_rate=0.92, strict=0.64, mrs_3m_us=0.1852 |

## Known Shortfalls (P2-1 regime-stratified IC)

Regimes with mean_reversion_strength (MRS = -ic_mean) < 0.05 at 3m horizon:

| Market | Regime | IC (3m) | MRS | Note |
|---|---|---|---|---|
| US | bear | -0.0271 | +0.0271 | Temperature signal weak in US bear markets |
| HK | bull | -0.0087 | +0.0087 | Near-zero signal in HK bull regimes |
| CN | bull | N/A | N/A | Insufficient bull-regime observations in fixture window |
