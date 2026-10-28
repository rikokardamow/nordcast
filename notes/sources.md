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
| revision behaviour | first print kept; revisions as new vintages; null price = suspended, published next working day | 26 apr 2026 00:15–08:15 dk wrong, not corrected | values for an mtu appear 7.5 min before its start | "errors will occur, and will generally not be corrected" | – |
| known breaks | 19 mar 2025, 2 jun 2025, 1 oct 2025, 4 mar 2026, mari (q1 2027) | – | – | imbalance + mfrr columns deleted | – |
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
| satisfied_demand, dominating_direction | isp end + 15 min | first print 6.5–10.3 min after isp end |
| imbalance_price_eur, afrr_up/down_mw | isp end + 45 min | filled in 5–20 min after the first print; afrr revised ~30 min after end |
| mfrr_up/down_mw | isp end + 60 min | not measured; archived every 5 min from 28 oct to measure |
| da_price_eur | 13:00 copenhagen the day before | nord pool results ~12:45 cet |
| wind_mw, solar_mw | isp end + 5 min | 5-min rows post before each 5 minutes ends |
| wind_fc_da_mw, solar_fc_da_mw | 18:30 copenhagen the day before | "updated close to 18:00 local danish time" (not 12:00 as backfill.md had) |
| wind_fc_1h_mw | isp start − 51 min | "might be updated until 1 minute before the forecast starts" |
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
| wind_mw / solar_mw | 58,021 each | 2025-03-01 |
| wind_fc_da_mw | 57,500 | 2025-03-01 |
| wind_fc_1h_mw | 57,421 | 2025-03-01 |
| solar_fc_da_mw | 57,884 | 2025-03-01 |
| esett direction / price | 134,051 each | 2021-11-01 |

training window (from 1 oct 2025): 37,690 target isps, 22,909 of them after the 4 mar 2026 break. 1,000,259 observations in all.

not used: `api.data.energinet.dk` (needs an energinet azure service principal); dmi harmonie (deferred: 611 mb per stac grib lead time, edr returned 429).
