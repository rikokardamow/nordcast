# backfill – history from inception to today

28 oct 2026. the record starts the day the cron starts, but the models need history before that: lightgbm to train on, the council (timestral, chronos-2, timesfm 2.5) to read as context, and a backtest to show what each would have done. energinet keeps the history, so pull it all once, load it as estimated vintages, and never touch it again.

## how history goes into an insert-only store

the observation table already has what this needs: `published_at` and `vintage_quality in ('exact','estimated')`. energy-forecasting does the same for eia history: the real publish time of an old row is unknown, so `published_at` is set from the release calendar and marked estimated. here:

- `published_at = observed_for + nominal_lag(series)`, `vintage_quality = 'estimated'`
- nominal lags, written down once in `sources/energinet.py` as a dict and tested: 5-min feed 5 min; `Forecasts_Hour` – forecast rows are published at their own issue time, which the dataset doesn't carry, so use the forecast type's definition (day-ahead at 12:00 the day before, intraday/current at the hour minus 1 h, 1-hour at minus 1 h, 5-hour at minus 5 h); `DayAheadPrices` 12:45 the day before; `ImbalancePrice` end of isp + 2 h for the first print (check against the live cron after a week and correct the constant); settlement: observed_for + 8 days.
- rows pulled by the live cron from now on get `published_at = pulled_at` and `vintage_quality = 'exact'`. the boundary date between estimated and exact is in the manifest.
- value_asof doesn't care which it is. the backtest notebook does: it reports results on estimated vintages separately and says so. nothing on estimated vintages is a record.

## what to pull and from when

step 0 of the backfill job: for every dataset, `?limit=1&sort=<timecol> ASC` and print the first row. that is the inception date; write it to `notes/inception.md` and don't trust what I've written below until it's checked.

what I expect, to be verified:

| series | dataset | expected from | resolution | note |
|---|---|---|---|---|
| imbalance, afrr_act, mfrr_act dk1/dk2 | PowerSystemRightNow | apr 2024 (pilot start) | 5 min | the columns exist earlier but are null before the pilot; filter nulls |
| wind_on, wind_off, solar, exchanges | PowerSystemRightNow | ~2019 | 5 min | production total is approximate per the catalogue; fine for features |
| fc_wind_* | Forecasts_Hour | a few years | hourly | energinet's own forecast, the baseline to beat for wind |
| price_da dk1/dk2 | DayAheadPrices | 1 oct 2025 | 15 min | before that: `Elspotprices`, hourly, from 1999-07-01; load both, separate series ids, don't stitch |
| price_imb dk1/dk2 | ImbalancePrice | 4 mar 2025 | 15 min | single-price since nov 2021, but this dataset starts mar 2025; nothing earlier to load |
| mfrr_cap, afrr_cap, fcr | mFRRCapacityMarket, afrr dataset, FcrNdDK2 | varies | daily/hourly | repo 3 only |
| settlement by type | ProductionConsumptionSettlement | 2020 | hourly | truth series for wind; late |
| balance by type | ElectricityBalanceNonv | ~2017 | hourly | faster than settlement |
| harmonie wind at six points | dmi | no archive on the open api | – | see below |

dmi has no free forecast archive (edr keeps 24 h, stac 48 h). open-meteo's historical forecasts (`dmi_harmonie_arome_europe`, has 100 m wind) exist but are non-commercial only; fine for a public research record, say so. so for history the weather feature is either (a) ecmwf era5 reanalysis at the six points, hourly, from cds (free key, `cdsapi`), which is truth not forecast and will make the backtest look better than live, or (b) nothing, and the backtest uses energinet's wind forecast error only. do (b) first and (a) as a separate column clearly named `era5_*` so I can't confuse the two. the live cron has had harmonie since day one, so after a few months the exact-vintage window is the honest test anyway.

volume: 5-min × 2 areas × ~10 columns × 7 years ≈ 15m rows into `observation`. supabase free tier is 500 mb. so: history goes to parquet under `data/history/` (committed to a release asset, not the repo), and only the window the live model and the council actually read goes into postgres: last 400 days for everything at 15-min, full history for the hourly and daily series. the notebooks read parquet via duckdb for anything older. this keeps `value_asof` cheap on the live path.

## the council

challengers in `freeze.make_calls(challengers=...)`, same shape as `timestral_model.py` in energy-forecasting: read history through value_asof, pinned checkpoint, return point/q10/q50/q90/model_version. none of them blocks the freeze.

- `challengers/timestral.py` – Timestral-209M, pinned revision, context 2048 steps.
- `challengers/chronos.py` – chronos-2 (I have the fork), pinned, context 2048 or the model max.
- `challengers/timesfm.py` – timesfm 2.5, pinned. the three together are the council; the headline call stays lightgbm until a challenger beats it over a pre-registered window (same rule as wpsr: swap only at a quarter boundary).

context is the point to be honest about: 2048 × 15 min is 21 days. the council never sees more history than that at inference, whatever is in the store. the backfill is for lightgbm's training set, the backtest and the baselines' lookbacks, not for the foundation models' context. if a model takes longer context (chronos-2 says 8192; check), use it and record `context_steps` in the row like the wpsr challenger records `context_weeks`.

one zero-shot each, no fine-tuning, no covariates in v1. covariates (wind forecast error) as a chronos-2 run in v2 if the zero-shot result is close to lightgbm.

## backtest

`notebooks/05_backtest_council.ipynb`, then `jobs/backtest.py` once the notebook is right (same order as wpsr: notebook first, job after). walk-forward over the estimated-vintage history, weekly refits for lightgbm, zero-shot for the council, persistence as the bar. scorecard per horizon: mae, rmse, sign, pinball, coverage, and the 10 mw pnl at `price_imb`. report two columns: all history (estimated vintages) and the exact-vintage window once it exists. never blend, never show the estimated-vintage result as the record.

## jobs

- `jobs/backfill.py` – step 0 inception probe, then full pull per dataset in monthly chunks with retries, raw json saved, parquet written, postgres loaded for the live window. idempotent: re-running adds 0 rows (test). takes an hour; run it once on the mac, not on actions.
- `jobs/backfill_era5.py` – optional, cds key, six points, 100 m wind, same parquet layout, series ids `era5.<point>.ws100`.

## tests

- nominal lag table: every series id has one; the live cron's `published_at` ≥ the estimated one for the same row (if it isn't, the lag constant is wrong).
- backfill idempotence.
- inception dates in notes/inception.md match `min(observed_for)` in the store.
- a challenger with fewer than `context_steps` of history raises, not guesses (the wpsr one does this at 52 weeks).

## regimes (from the 28 oct research)

the history is not one market. backtests and the replay split on these and never pool across a break without a regime flag:
- before 4 mar 2025: old balancing design, hourly imbalance price (not in ImbalancePrice anyway)
- 4 mar – 1 jun 2025: nordic mfrr eam live, spikes (dk2 near dkk 75/kwh), avg imbalance cost ~4x
- 2 jun 2025 onward: 25 mw threshold, the 'none' direction appears
- 1 oct 2025 onward: 15-min day-ahead. the only window that's 15-min on every layer, ~13 months
- mari accession, no firm date, sep–oct 2027 likely (was q1 2027; notes/mari-plan.md). retrain after it.
