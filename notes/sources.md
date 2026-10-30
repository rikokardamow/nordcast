# sources – data register

28 oct 2026. one block per dataset, per controls.md §1. the target moved: `PowerSystemRightNow` no longer has imbalance or mfrr columns (energinet deleted them; see its `caution`), so the call is on `ImbalancePrice` (decided 28 oct, see "target" below).

## target

- **volume:** `ImbalancePrice.SatisfiedDemand`, dk1, mw, per 15-min isp.
- **direction:** `ImbalancePrice.DominatingDirection`, dk1, integer 1 / 0 / -1.
- scored against the first vintage the archive captured; later vintages kept, scored separately.
- **not** total system imbalance: it's the mfrr volume. aFRR is in separate columns (`aFRRUpMW`, `aFRRDownMW`).

## the sign check (phase 0b)

stated by energinet (`/meta/dataset/ImbalancePrice`, read 28 oct 2026):
- `SatisfiedDemand` (MW): "A positive sign indicates mFRR upregulation. A negative sign indicates mFRR downregulation."
- `DominatingDirection` (integer): "1 for upregulation, 0 for no regulation and -1 for downregulation."

tested on every isp from 4 mar 2025 11:15 utc to 28 oct 2026 (115,832 rows, both areas). agreement with `DominatingDirection` over isps where it isn't 0:

| dk1 | isps with direction | isps 'none' | sign(SatisfiedDemand), + = up | + = down | sign(TotalmFRRUp − TotalmFRRDown), + = up | + = down | 'none' with SatisfiedDemand = 0 |
|---|---|---|---|---|---|---|---|
| 4–18 mar 2025 | 1,388 | 2 | 100.0 % | 0.0 % | 99.8 % | 0.2 % | 100.0 % |
| 19 mar – 1 jun 2025 | 7,179 | 15 | 100.0 % | 0.0 % | 99.9 % | 0.1 % | 100.0 % |
| 2 jun – 30 sep 2025 | 10,412 | 1,202 | 100.0 % | 0.0 % | 100.0 % | 0.0 % | 100.0 % |
| 1 oct 2025 – 3 mar 2026 | 12,813 | 1,968 | 100.0 % | 0.0 % | 100.0 % | 0.0 % | 100.0 % |
| 4 mar 2026 – | 18,745 | 4,176 | 100.0 % | 0.0 % | 99.9 % | 0.1 % | 92.3 % |

dk2 is the same to 0.1 % in every window. the activation columns (`MfrrEnergyActivationMarket.TotalmFRRUpMW`/`DownMW`) are both positive magnitudes, so their direction is up minus down.

the convention is yours to confirm; the data says positive = up, with no exception.

## regime breaks seen in the data

- **19 mar 2025:** imbalance price and dominating direction switch from the pricing module to the new design.
- **2 jun 2025:** 'none' appears in volume (25 mw threshold).
- **4 mar 2026 (not in the notes):** `SatisfiedDemand` changes meaning. before, it was the mfrr *demand* (balancing demand) in the zone; from 4 mar 2026 it's the mfrr *activated* to cover it, and dominating direction is set from that. since then 7.7 % of dk1 'none' isps have a non-zero `SatisfiedDemand`.
- 'none' share in dk1 since 4 mar 2026: 18 % of isps, not ~10 %.

## register

| field | ImbalancePrice | MfrrEnergyActivationMarket | mfrrRequest | PowerSystemRightNow | ElectricityProdex5MinRealtime |
|---|---|---|---|---|---|
| endpoint | api.energidataservice.dk/dataset/ImbalancePrice | …/dataset/MfrrEnergyActivationMarket | electricitymarketservice.energinet.dk/api/v1/PublicData/dataset/mfrrRequest | …/dataset/PowerSystemRightNow | …/dataset/ElectricityProdex5MinRealtime |
| use | target (volume + direction), price | cross-check | feature | feature | feature |
| resolution | 15 min | 15 min | 15-min mtu, issued each minute | 1 min, dk total + per-area exchanges, afrr | 5 min, per area |
| key columns | TimeUTC, PriceArea, SatisfiedDemand (MW), DominatingDirection, ImbalancePriceEUR/DKK, SpotPriceEUR, aFRRUpMW, aFRRDownMW, mFRRMarginalPrice* | TimeUTC, PriceArea, mFRRSAUpReqMW, mFRRSADownReqMW, TotalmFRRUpMW, TotalmFRRDownMW | timeStamp, mtuStart, area, value (MW, ±; sign not stated) | Minutes1UTC, OffshoreWindPower, OnshoreWindPower, SolarPower, Exchange_*, aFRR_ActivatedDK1/DK2 | Minutes5UTC, PriceArea, production by type, exchanges |
| licence | energi data service terms | same | same | same | same |
| republish raw? | yes, with attribution | yes | yes | yes | yes |
| attribution | "data: energinet, energi data service" | same | same | same | same |
| cost | 0 | 0 | 0 | 0 | 0 |
| rate limit | http 429; back off 60 s | same | ≤ 1 req/s recommended | same | same |
| history start | 4 mar 2025 11:15 utc | 3 mar 2025 23:00 utc | 7 days only (rolling) | (inception probe, step 2) | (step 2) |
| revision behaviour | first print kept; revisions as new vintages; null price = suspended, published next working day | 26 apr 2026 00:15–08:15 dk wrong, not corrected | values for an mtu appear 7.5 min before its start; `timeStamp` is the issue time to the aof, up to ~20 min earlier, **not** the publication time (series `mfrr_request_public` since 29 oct 2026; the first series, published at timeStamp, leaked and is superseded) | "errors will occur, and will generally not be corrected" | – |
| known breaks | 19 mar 2025, 2 jun 2025, 1 oct 2025, 4 mar 2026, mari (no firm date; sep–oct 2027 likely, notes/mari-plan.md) | – | – | imbalance + mfrr columns deleted | – |
| archived since | 28 oct 2026 18:16 utc, every minute, last 2 days | not archived (history is kept) | 28 oct 2026, every minute, last 30 min | 28 oct 2026, last 30 min | 28 oct 2026, last 30 min |
| verified on | 28 oct 2026, api metadata + full-history check above | same | 28 oct 2026, api guide page | 28 oct 2026, api metadata | 28 oct 2026, api sample |

## added in step 2 (backfill)

| field | DayAheadPrices | Forecasts_5Min | eSett EXP14/Prices |
|---|---|---|---|
| endpoint | …/dataset/DayAheadPrices | …/dataset/Forecasts_5Min | api.opendata.esett.com/EXP14/Prices?mba=10YDK-1--------W |
| use | feature | feature (wind onshore + offshore, solar; day-ahead and 1-hour columns) | cross-check of price and direction |
| resolution | 15 min | 5 min, averaged to the isp only when all three are there | 15 min (quarters identical within an hour before 19 mar 2025) |
| licence / attribution | energi data service terms; "data: energinet, energi data service" | same | esett open data terms (not read in full; check commercial use); "data: esett open data" |
| history start | 2025-10-01 (hourly `Elspotprices` before, not loaded) | 2019-10-10 (loaded from 2025-03-01) | 2021-11-01 |
| revision behaviour | – | each column overwritten in place; only the archive (from 28 oct 2026) keeps versions | unpublished isps return 0.0 in every column; dropped, never loaded |
| verified on | 28 oct 2026, `dataFrom` + backfill | same | 28 oct 2026, backfill: direction = energinet's in 99.35 % of 57,877 isps; price within 0.01 € in 98.1 % of 57,893 |

`ElectricityProdex5MinRealtime` history starts 2015-01-01 (loaded from 2025-03-01). `dataFrom` in the metadata is danish local time.

## nominal lags (estimated vintages)

backfilled rows have `published_at` = isp start + the lag below and `vintage_quality = 'estimated'`; the table is `NOMINAL_LAG` in `sources/energinet.py` and `sources/esett.py`, tested. every lag errs late, so history never shows a value earlier than it really was (the opposite of backfill.md's "live ≥ estimated" check). measured on the archive's first hour, 28 oct 2026; re-measure after a week.

| series | estimated published_at | measured / stated |
|---|---|---|
| satisfied_demand, dominating_direction | isp end + 15 min | first print 6.5–10.3 min after isp end (28 oct); on 28–29 oct median 6.8, but ~22 min in 3 of 16 watched isps, past the lag: re-measure after a week, then 25 min with the next re-backfill (docs/experiments/first-print-lags) |
| imbalance_price_eur, afrr_up/down_mw | isp end + 45 min | filled in 5–20 min after the first print; afrr revised ~30 min after end |
| mfrr_up/down_mw | isp end + 60 min | measured 28–29 oct: posts ~4.5 min before the isp starts (scheduled ahead), 6 isps (docs/experiments/first-print-lags) |
| da_price_eur | 13:00 copenhagen the day before | nord pool results ~12:45 cet |
| wind_onshore_mw, wind_offshore_mw, solar_mw, residual_load_mw, flow_{de,nl,gb,no,se,dk2}_mw | isp end + 5 min | 5-min rows post before each 5 minutes ends; isp complete at most 2.9 min after its end (17 isps, 28–29 oct) |
| wind_onshore_fc_da_mw, wind_offshore_fc_da_mw, solar_fc_da_mw | 18:30 copenhagen the day before | "updated close to 18:00 local danish time" (not 12:00 as backfill.md had) |
| wind_onshore_fc_1h_mw, wind_offshore_fc_1h_mw | isp start − 51 min | "might be updated until 1 minute before the forecast starts" |
| esett price, direction | isp end + 2 h | ~1 h (research note) |
| mfrr_request | exact: each issue's `timeStamp` | from 7.5 min before the mtu; 7 days kept upstream |

## row counts after the backfill (28 oct 2026, dk1, isp level)

| series | rows | from |
|---|---|---|
| satisfied_demand | 57,887 | 2025-03-04 11:15 utc |
| dominating_direction | 57,902 | 2025-03-04 11:15 |
| imbalance_price_eur | 57,917 | 2025-03-04 11:15 |
| afrr_up_mw / afrr_down_mw | 57,918 each | 2025-03-04 11:15 |
| mfrr_up_mw / mfrr_down_mw | 57,969 each | 2025-03-03 23:00 |
| da_price_eur | 37,820 | 2025-10-01 |
| wind_onshore_mw / wind_offshore_mw | 58,024 each | 2025-03-01 |
| solar_mw | 58,021 | 2025-03-01 |
| wind_onshore_fc_da_mw / wind_offshore_fc_da_mw | 57,692 / 57,500 | 2025-03-01 |
| wind_onshore_fc_1h_mw / wind_offshore_fc_1h_mw | 57,642 / 57,470 | 2025-03-01 |
| solar_fc_da_mw | 57,884 | 2025-03-01 |
| residual_load_mw (29 oct) | 58,122 | 2025-03-01 |
| flow_de/nl/gb/no/se/dk2_mw (29 oct) | 58,122 each | 2025-03-01 |
| esett direction / price | 134,051 each | 2021-11-01 |

wind by type (28 oct 2026): the 5-min feed and `Forecasts_5Min` define offshore differently (substation vs generator location), and dk1 offshore production runs ~900 mw above its forecast (27 oct 11:00 utc: 2,000 against 1,094 mw, onshore within 10 mw). so each error is taken within its type; the combined `wind_mw`, `wind_fc_da_mw` and `wind_fc_1h_mw` keep their rows but get no new ones (migration 20261028210000).

training window (from 1 oct 2025): 37,690 target isps, 22,909 of them after the 4 mar 2026 break. 1,000,259 observations in all after the first backfill; 1,346,620 backfilled rows after the wind split.

## power layers (added 29 oct 2026)

from `ElectricityProdex5MinRealtime`, no new api calls; migrations 20261029200000 and 20261029210000; docs/layers/.

| series | built as | checked against | result |
|---|---|---|---|
| residual_load_mw (#32) | ProductionLt100MW + ProductionGe100MW + the six exchange columns = demand − wind − solar | `ProductionConsumptionSettlement`, hourly: central + local + commercial + hydro + unknown + exchanges | correlation 1.000 on 1–7 aug and 1–7 oct 2026, mean +50 / −2 mw; a fixed-week test pins it |
| flow_de/nl/gb/no/se/dk2_mw (#33) | one exchange column each | the same dataset's exchange per border | correlation 1.000 (great belt 0.999), bias within ±12 mw; a fixed-week test per border |

- **sign:** every real-time exchange column is + = import (tested per border against settlement, which states it).
- **not added:** a derived real-time consumption (production + net import) runs up to ~700 mw low at summer midday: the 5-min `SolarPower` misses part of rooftop solar (614 vs settlement 740 mw, 1–7 aug 2026). residual load doesn't have the problem.
- **no open capacity or scheduled flows** on energi data service for dk1's borders (entso-e needs a token; jao). #33 uses an observed limit instead.
- **`DayAheadPrices` covers DE, DK1, DK2, NO2, SE3, SE4.** layer #31's neighbour prices are cached outside the record (`data/history/DayAheadPricesAll/`, gitignored); the record stays dk1-only.
- **`ProductionConsumptionSettlement`** (hourly, published daily) changed method on 1 sep 2026 (datahub 3.0); used only as a check.

## weather (added 29 oct 2026)

| field | open-meteo previous-runs api, dmi harmonie |
|---|---|
| endpoint | previous-runs-api.open-meteo.com/v1/forecast?models=dmi_harmonie_arome_europe |
| use | feature (not yet in a model): 100 m wind speed and direction at six dk1 points: horns rev and anholt (offshore), rømø, hvide sande, hanstholm, skagen |
| resolution | hourly, yesterday to two days ahead per pull |
| licence | data cc by 4.0, "weather data by open-meteo.com"; the free api is for non-commercial use, which this public research record is |
| republish raw? | yes, with attribution |
| cost / key | 0 / none |
| history start | `previous_day1` (the run about a day earlier) back to ~jul 2024, per the 28 oct research; not backfilled yet |
| revision behaviour | each model run replaces the forecast; the archive keeps every version with its pull time (every 15 min) from 29 oct 2026 21:00 utc |
| why not dmi directly | dmi's edr point service answered 429 ("server is busy") to every try on 28 and 29 oct; its stac grib files are 611 mb per lead time |
| verified on | 29 oct 2026, live pull: 432 rows (6 points × 72 h), a second pull added 0 |

| field | copernicus cds, era5 single levels |
|---|---|
| endpoint | `reanalysis-era5-single-levels` via `cdsapi` (jobs/backfill_era5.py) |
| use | truth, not a forecast: `era5.<point>.ws100` at the same six points, nearest 0.25° cell, parquet only under `data/history/era5/`. never a forecast or live feature |
| resolution | hourly |
| licence | cc by 4.0; must be accepted on the dataset page, per account |
| cost / key | 0 / free key in `~/.cdsapirc` |
| limits | a 31-day month estimates at about 8,900 of a 121,000 request limit (scaled from one day, 30 oct 2026). no published rate numbers; cds asks for sequential requests and may disable accounts over parallel or repeated invalid ones |
| revision behaviour | preliminary era5t is replaced after 2–3 months, so the job takes a month only 90 days after it ends |
| not used | `reanalysis-era5-single-levels-timeseries`: its catalogue entry ended 6 dec 2024 when checked on 30 oct 2026 |
| verified on | not yet: no data pulled, the era5 licence isn't accepted. the file reader is tested on a synthetic file only |

mfrrrequest's lead, 29 oct 2026: at a 15-min freeze the newest public request is for the isp before the target; on the 25 isps measurable so far it correlates 0.36 with the target (30 min: −0.26 on 22). too few to judge; measure again once the archive has weeks. the leaked first series had shown 0.68.

not used: `api.data.energinet.dk` (needs an energinet azure service principal); dmi harmonie (deferred: 611 mb per stac grib lead time, edr returned 429).
