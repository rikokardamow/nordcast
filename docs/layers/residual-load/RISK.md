# Residual load layer (#32, DK1): risk analysis (written before any code)

29 Oct 2026. Claimed from the energy-forecasting catalogue (`docs/PROJECTS.md` #32, "Renewables and Residual Load", grade 8), which plans #31–#34 for this repo; the energy-forecasting session confirmed nobody else had started it. Built in `~/nordcast` on `main`, uncommitted until approved.

## Facts checked today

- **No measured real-time consumption is published for DK1.** `ElectricityProdex5MinRealtime` (5-min) has production (<100 MW, ≥100 MW), offshore wind, onshore wind, solar and six exchange columns, no consumption. `ProductionConsumptionSettlement` has `GrossConsumptionMWh`, but hourly and published daily, with a method change on 1 Sep 2026 (DataHub 3.0).
- **Exchange sign, tested, not read:** on 1–7 Oct 2026 (168 h, DK1), each real-time exchange column correlates 1.000 (Germany, Norway) and 0.999 (Great Belt) with the settlement column of the same border, whose stated sign is + = import. So the real-time columns are **+ = import** too.
- **Derived consumption fails in summer.** All production + net import, per 5 min, against settlement gross consumption: 1–7 Oct 2026, correlation 0.991, mean +78 MW, MAE 85 MW (on 2,741 MW); 1–7 Aug 2026, correlation 0.845, mean −339 MW, the gap sun-shaped (about −700 MW at 08–12 UTC, correlation −0.6 with solar). The 5-min `SolarPower` misses part of distributed rooftop solar (614 vs settlement 740 MW that week), and self-consumption isn't in the feed at all. **So the layer does not publish consumption.** (With the sign flipped, October's correlation is 0.23: the sign test above holds.)
- **Residual load is measured exactly.** By energy balance, consumption − wind − solar = thermal production + net import, and solar the feed can't see drops out of both sides. `ProductionLt100MW` is thermal (local CHP and commercial plants: correlation 0.85 / 0.96 with settlement, negative with wind and solar), `ProductionGe100MW` the central plants (0.99). Real-time residual load = both + the six exchanges, against settlement's central + local + commercial + hydro + unknown + exchanges: **correlation 1.000 in both weeks**, mean +50 MW (Aug, old method) and −2 MW (Oct), MAE 51 and 24 MW. The energy-analyst skill's reference (`gas-power-metals.md` §C3) defines it as "demand − wind − solar per settlement period"; nuclear/must-run variants don't apply (Denmark has no nuclear). It can be negative: −108 MW mean on 1–7 Aug 2026, when DK1 exported its surplus.
- **No open DK1 consumption forecast.** Energinet's `Forecasts_5Min` / `Forecasts_Hour` carry wind and solar only. So this layer measures residual load; any residual-load forecast error it reports is the renewables' part only.
- **History:** the backfill cache holds the 5-min feed from Mar 2025, with no nulls in the production or exchange columns in Mar 2025, Oct 2025 or Oct 2026.

## Risks, ranked

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | **Touching the live record.** The record and the pre-registered challenger are running; nordcast-plan.md builds nothing outside its phases. | Medium | High | The layer adds two series and their rows only. No change to `features.SERIES`, the frozen calls, the challenger's inputs or `notes/preregistration.md`. A finding that residual load helps goes into a v2 model card, never into lightgbm_v1. |
| 2 | **Publishing a consumption number the feed can't support.** | Certain | High | Dropped: no consumption series. Only residual load, labelled "thermal production + net import (= demand − wind − solar)". A test on a recorded week asserts it against settlement: correlation > 0.99, bias under 100 MW. |
| 3 | **The sign flips or a column is renamed.** | Low | High | The fixed-week test above fails on either. One missing column drops the ISP (`isp_values` needs every piece), so a renamed column shows as a hole, not as a wrong number. |
| 4 | **Overclaiming a forecast.** Without a consumption forecast there is no residual-load forecast. | High | Medium | The README says so first. The "is it alpha" test uses only what is known at the freeze. |
| 5 | **Leakage in the test.** | Medium | High | Every value read through history-as-of with the 5-min feed's nominal lag (ISP end + 5 min); features at isp − h − 5 min, as in training; out of sample by quarter (the replay's rounds), Diebold–Mariano on the loss differential. |
| 6 | **Hard-coding a peak window.** | Medium | Low | The peak window is derived from the data per season (energy-analyst, `gas-power-metals.md` §C3), never fixed. |
| 7 | **Settlement method change, 1 Sep 2026.** | Certain | Low | The bias check runs on one week before and one after, and both are reported. |
| 8 | **Clashing with other sessions.** A quality pass is open on `store.py`, `quality.py`, `backup.py`, `conftest.py`. | Low | Medium | This layer touches `sources/energinet.py` (two `SERIES` entries), one new migration, a new module, tests and `docs/layers/residual-load/`. Not the other session's files. |
| 9 | **Load on Energi Data Service.** | Low | Low | No new dataset is pulled: both series come from the 5-min feed the archive and backfill already pull. |

## Stop conditions

- Residual load's correlation with settlement falls under 0.99 on either check week.
- The test needs a feature that isn't public by the freeze.
- Anything requires changing the frozen record or the challenger.
