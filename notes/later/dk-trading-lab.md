# dk trading lab – build notes

28 oct 2026. the denmark-focused set. five separate repos, one shared data package, one shared point-in-time module. this file is what I hand to claude code before each repo, so it carries the stack, the apis, the fields and the scoring, not just the idea.

## shared stack

- python 3.12, uv for envs, ruff. no poetry.
- duckdb + parquet for everything stored. one `data/` folder per repo, gitignored, rebuilt by `pull.py`.
- pandas for the small stuff, polars where the real-time feed gets big (5-min rows × 2 areas × months).
- lightgbm for the small models. torch only if a notebook proves it's needed.
- mapie for intervals, arch for garch, statsmodels for the boring tests. pysr only in repo 2.
- highspy (the highs solver) for the battery lp in repo 3. no gurobi.
- ecmwf-opendata client + xarray + cfgrib for the 0.25° global pulls. eccodes via conda-forge or the wheel, whichever installs on the mac mini first.
- dmi-open-data (github.com/edu230991/dmi-open-data) for harmonie. 
- plotly for the interactive charts, matplotlib for the png that goes in the readme and the post. navy on white, light blue second series, grey band, one annotation.
- github actions cron for anything that has to run on a schedule. secrets in repo settings, `.env` locally, never committed.
- pytest, small. one test per pull function that checks columns and row count on a fixed day.
- `pit` module (freeze / hash / score) lifted out of energy-forecasting into its own tiny package, `pip install -e ../pit`. every repo imports it. manifest fields: business_date, knowledge_cutoff_utc, model_id, inputs_sha256, output_sha256, git_sha.

## shared data package: `dkdata`

lives in energy-data-scraper as a subpackage, or its own repo if that gets messy. one module per source. every function returns a dataframe with a `pulled_at_utc` column and utc timestamps. no caching logic inside; the caller writes parquet.

### energinet – energi data service (free, no key, 1 req/s)

base: `https://api.energidataservice.dk/dataset/{Dataset}`
params: `start=2026-10-01T00:00`, `end=2026-10-28T00:00` (end exclusive), `filter={"PriceArea":["DK1","DK2"]}`, `columns=...`, `limit=0` for no cap, `sort=HourUTC ASC`. `start=now-P7D` works.
response: `{"total": n, "records": [...]}`.

datasets I need, with the columns that matter (check the dataset page for exact names, they rename things during the 2026 datahub upgrade):

- `DayAheadPrices` – TimeUTC, TimeDK, PriceArea, DayAheadPriceEUR, DayAheadPriceDKK, 15-min from 1 oct 2025. `Elspotprices` (HourUTC, SpotPriceEUR, hourly from 1999) stopped 30 sep 2025; keep it as a separate series.
- `ImbalancePrice` – TimeUTC, TimeDK, PriceArea, ImbalancePriceEUR, ImbalancePriceDKK, SpotPriceEUR, DominatingDirection, afrr/mfrr price fields. 15-min, **history only from 4 mar 2025**. preliminary settlement day 2, final after day 13. keep every pull, never overwrite (repo 4 depends on that).
- `PowerSystemRightNow` – Minutes5UTC, PriceArea, ProductionGe100MW, ProductionLt100MW, OffshoreWindPower, OnshoreWindPower, SolarPower, Exchange_* (DE, NO, SE, NL, GB via viking? check), and since the 2024 pilot: Imbalance DK1/DK2 (mw the system would see without tso action), aFRR activated, mFRR activated. this is the nowcast target.
- `Forecasts_Hour` – ForecastType (Onshore Wind, Offshore Wind, Solar), ForecastDayAhead, ForecastIntraday, ForecastCurrent, Forecast5Hour, Forecast1Hour. energinet's own wind forecast, the thing to beat.
- `ProductionConsumptionSettlement` – settled hourly production by type and exchanges. the truth series, published late.
- `ElectricityBalanceNonv` – hourly balance by technology, faster than settlement.
- `mFRRCapacityMarket`, `FcrNdDK2`, and the afrr capacity dataset – clearing prices for the stack in repo 3.
- `Transmissionlines` or whatever the current name is for scheduled and physical cross-border flows – DK1–DE, DK1–NO2, DK1–SE3, DK2–SE4, DK2–DE (kontek), DK1–NL (cobra), DK1–GB (viking). repo 2 and 4 need scheduled vs physical.

real-time api (separate, 1 req/s, 7 days of history max):
base: `https://electricitymarketservice.energinet.dk/api/v1/PublicData/dataset/{Dataset}/latest` and `/period?from=&to=`. mfrr request (energinet's live mfrr need) is here since march 2026. pull every 5 min on cron, append to parquet, because it only keeps a week.

### dmi – harmonie dini (free, no key since 2 dec 2025 on opendataapi.dmi.dk; fair use 500 requests / 5 s)

- edr api for point/box queries on `opendataapi.dmi.dk` (old `dmigw.govcloud.dk` host still wants keys; don't use it). edr keeps the last 24 h only, stac the last 48 h, so the archive is mine to keep from day one. the edr `/grib` endpoint goes on 1 nov 2026; use stac for grib. 100 m wind in grib is `100u`/`100v` on the model grid and needs rotating.
- stac api for whole grib files when I need the grid: `https://dmigw.govcloud.dk/v1/forecastdata/collections/harmonie_dini_sf/items?...` then download, open with cfgrib. 2 km, hourly, 2.5 days, new run every 3 h. this is the one that matters for danish wind; ecmwf 0.25° is 12× coarser.
- eps collections (`harmonie_dini_eps_means`, `_percentiles`) for the spread of the short-range forecast. feeds the risk layer.
- observations api for station wind as the truth for forecast error (anholt, thyborøn, hvide sande, rømø, the usual coast stations).
- fallback with no key and no rate limit: open-meteo's dmi endpoint (`api.open-meteo.com/v1/dmi`), same harmonie dini, hourly, point queries. good enough for the first notebook; swap to dmi direct for anything frozen.

### ecmwf open data (free, 2 h delay on the 9 km, real-time on 0.25°)

- `ecmwf-opendata` client, `Client(source="ecmwf", model="ifs")`, `retrieve(type="fc", step=[0..48], param=["10u","10v","100u","100v","2t","msl"], ...)`. 0.25° now, try the 9 km subset once the pull works. area box for repos 1–2: 3°E–16°E, 53°N–59°N (north sea, jutland, kattegat, german bight).
- ens for the regime work later: `type="pf"`, members, 0.25° only. not in the first cut.

### entso-e transparency (free key, `entsoe-py`)

backstop and cross-check for day-ahead (DK1 = 10YDK-1--------W, DK2 = 10YDK-2--------M), scheduled exchanges, and the german price for repo 2 (DE-LU = 10Y1001A1001A82H). energinet's own datasets are cleaner for dk; use entso-e for the non-dk legs.

### what I don't have and will say so

- epex / nord pool continuous intraday order book and trade ticks for dk1/dk2. paid. repo 5 simulates and says so. nord pool's free pages give hourly intraday vwap for some areas; check if dk is included and use it as a sanity series.
- energinet's intraday schedules at unit level. not public.

## the five repos

### 1. nordcast (dk1 imbalance nowcast)

question: can I nowcast the dk1 system imbalance (mw) 15, 30 and 60 min ahead better than persistence, using the 5-min real-time feed plus a wind-forecast error signal.

target: `PowerSystemRightNow` dk1 imbalance, 5-min, aggregated to 15-min isp. column name, start date and sign convention are **not verified** – read `/meta/dataset/PowerSystemRightNow` and the real-time imbalance q&a in a browser before step 3. since 2 jun 2025 energinet ignores mfrr needs under 25 mw, so ~1 in 10 dk1 isps has no dominating direction and settles at day-ahead. the call is two-part: direction (up / down / none) as a classifier, then volume. the scorecard scores both.

features, all available at prediction time:
- last 12 × 5-min imbalance values, afrr activated, mfrr activated
- live wind production minus energinet's `Forecast1Hour` / `ForecastCurrent` for the same hour (forecast error, the main driver)
- harmonie dini 10 m / 100 m wind at 4–6 coastal points, latest run, step matching the target time, and the change between the last two runs (forecast revision)
- hour, weekday, day-ahead price level, scheduled exchange on the dc links (ramps at the hour boundary cause structural imbalance)
- mfrr request from the real-time api: published 7.5 min before each isp starts, so the 15-min call can't see its own isp's request, only the previous ones. archive it every minute; it keeps 7 days.

models: persistence (baseline), persistence + mean reversion, lightgbm per horizon, and one chronos zero-shot run for the comparison. mapie for 10/90 bands.

scoring: mae and rmse by horizon vs persistence; direction accuracy (3-class, with the none class); pinball; coverage. nord pool continuous intraday closes 60 min before delivery, so the 15/30-min calls can't be traded intraday: the trading translation is the hold-into-imbalance decision (deliberately leave 10 mw open in the nowcast direction, settled at the imbalance price), which denmark's single-price settlement allows. the 60-min call is the last one that can still be traded on idc. expected skill from the literature: ~15–25 % over persistence at 15 min (austrian imbalance price 2605.09061: 18.6 % on quantile loss).

live: github actions every 15 min, pulls, predicts, writes a row to `calls/` with the `pit` manifest, scores the rows whose outcome is in. this is the "production-level python that runs" item. no notebook in the loop.

first-notebook version (what I ship by friday if I need to): one day of history pulled, persistence vs lightgbm on 15-min horizon, one chart of nowcast vs actual for a windy day. that's enough to link.

### 2. dk1-de-spread-wind-regime

question: when does dk1 decouple from germany, and is it the wind-forecast gap between jutland and north germany.

data: DayAheadPrices DK1, entso-e DE-LU day-ahead, energinet Forecasts_Hour (dk wind), german wind forecast from entso-e (A69 generation forecast for DE), scheduled flow on DK1–DE, harmonie dini wind at jutland points vs ecmwf 0.25° wind over schleswig-holstein / lower saxony boxes.

method: spread = DK1 − DE, hourly. scatter vs (dk wind fcst / dk demand) − (de wind fcst / de demand), coloured by flow direction and by whether DK1–DE is at capacity. pysr on the spread with those features, complexity ≤ 12, pick the simplest equation within 10 % of best loss. then a regime split: the equation on days when the two wind forecasts correlate > 0.8 vs < 0.5.

output: two charts, one equation, one paragraph on what a dk1 intraday desk would do with it (the spread is tradeable through the dc link schedules and the de intraday).

### 3. bess-dk-rolling-intrinsic

question: what does a simple battery earn in dk1 across day-ahead, intraday-proxy and the balancing stack, and how much of october came from two days.

asset: 10 mw / 20 mwh, 90 % round-trip, one full cycle a day cap, no degradation in v1.

markets and data: DayAheadPrices (da), ImbalancePrice (as the settlement price for a deliberate imbalance strategy and as the intraday proxy), FcrNdDK2 / afrr / mFRRCapacityMarket clearing prices for the capacity stack. dk2 has the better fcr data; run both areas.

method: rolling intrinsic as the baseline (re-solve the lp each hour with new info, highs). then the kit/oxford idc paper's point: rolling intrinsic is myopic; compare against perfect foresight (upper bound) and against a stacking lp that reserves capacity for afrr/fcr. report captured spread as % of perfect foresight.

output: cumulative pnl chart, monthly bar by revenue stream, a table of the top five days. the post number is "x % of october pnl came from y days".

### 4. imbalance-settlement-audit

question: how different is the first-published dk imbalance price from the final one, and what did that cost someone settling early.

data: `ImbalancePrice` pulled every day and stored with pulled_at, never overwritten. I don't have the history of revisions yet, so this repo starts the moment the cron starts; backfill is impossible. same for `ProductionConsumptionSettlement` (first edition after 8 days, updated after 3 months, corrections up to 2 years per energinet's catalogue).

method: bitemporal table in duckdb (valid_time, knowledge_time, value). for each isp: first value, final value, number of revisions, sign changes, days to final. then: a 10 mw deliberate short settled at the first-published price vs the final — the settlement pnl error distribution.

output: the revision-lag chart (days to final on x, share of isps on y), the sign-change count, and one paragraph in settlement language. this is the cantor line and the accenture data-quality line in one repo. it runs forever and gets more interesting every month.

### 5. idc-execution-sim

question: how should a 50 mw wind-forecast revision be worked into the continuous intraday for a dk1 hour, and what's the cost of urgency.

data: none public. simulate: a hawkes-driven order flow calibrated to published german idc stylised facts (the amsterdam paper gives the parameters), dk1 liquidity scaled down by a factor I state. the day-ahead price and energinet's forecast revisions set the "signal" that triggers the parent order.

method: twap, vwap-ish, and the hawkes-aware schedule from the paper. impact vs time-to-delivery curves. one chart.

output: the execution-cost frontier and a paragraph on why it's the same problem as working a bond order with a thinner book. the point of this repo is the framing, not the number.

## repo skeleton (every one)

```
<repo>/
  README.md          three lines + one png
  pyproject.toml
  pull.py            dkdata calls → data/*.parquet
  features.py
  model.py
  score.py
  run.py             the thing cron calls, no notebook
  calls/             pit manifests + outputs, committed
  data/              gitignored
  notebooks/
    01_pull_and_look.ipynb
    02_baselines.ipynb
    03_model.ipynb
    04_intervals.ipynb
  notes/
    <repo>.md        this section, pasted, kept current
  .github/workflows/run.yml
  tests/test_pull.py
```

## order and time

1 first, one-notebook version this week, the cron version over the next two weekends. 4 starts its cron the same day as 1 because it needs the history to accumulate. 2 and 3 are the linkedin posts and take a weekend each. 5 last, it's a weekend.

## keys to register now

- dmi: none needed on opendataapi.dmi.dk.
- entso-e: have it.
- ecmwf open data: no key.
- energinet: no key. per-dataset rate limits since may 2026 (http 429, back off ~60 s).
