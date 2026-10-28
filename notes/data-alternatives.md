# data alternatives – stronger training data for da → id → imbalance in dk1

28 oct 2026. what free data exists beyond `ImbalancePrice` for the dk1 path day-ahead price → intraday price → imbalance price, and for mfrr volume/direction per 15-min isp. every "verified" line below is from a real call made today (18:30–19:00 utc); anything i couldn't call is marked unverified. nothing here is wired in yet; `sources.md` stays the register.

## what i measured

dk1, hourly unless said, 1 oct 2025 – 27 oct 2026, target = `ImbalancePrice.SatisfiedDemand` (mean per hour).

| feature | corr with target | n | note |
|---|---|---|---|
| wind+solar, `ForecastCurrent − ForecastDayAhead` (Forecasts_Hour) | −0.108 (pre 4 mar 2026: −0.165, after: −0.060) | 9,263 h | shortfall vs da forecast → up-regulation. when \|error\| > 200 mw the sign calls the direction right 58 % of the time (3,058 h) |
| same, `− Forecast5Hour` | −0.112 | | |
| same, `− Forecast1Hour` | −0.195 | | strongest single number i found. the error left *after* intraday trading is what reaches balancing |
| same, `− ForecastIntraday` | −0.073 | | |
| eSett imbalance no2 (15 min) | −0.104 | 36,437 isp | no1 −0.05, fi −0.01. weak, and 13 days late (see esett) |
| target, 24 h ago | +0.109 | | the persistence floor for day-ahead calls |
| nord pool id qh vwap vs imbalance price, 27 oct only | +0.62 (last-1h vwap +0.67; da +0.71) | 96 isp | one day, nothing to conclude; shows the data is usable |
| eSett dk1 price vs eds `ImbalancePriceEUR`, sep 2026 | 99.4 % equal to 0.01 €, 17 rows eSett 0.0 | 2,880 isp | eSett direction = eds `DominatingDirection` 100 % |

none of these is large. the target is mostly unexplained by public data a day ahead; the measurable signal is in the last hour (matches jacobazu's backtest: 4.9 % log-loss gain next hour, 1.5 % day-ahead).

## energi data service – datasets not yet used

the catalogue (`/meta/dataset`, 100 entries, read today) has **no intraday price dataset**. `NordpoolMarket` (had elbas avg/min/max) stopped may 2021. probed names `IntradayPrices`, `IntradayAuction*`, `Intraday` → 204 (don't exist).

| dataset | dk1 | resolution | history (verified) | lag / vintages | adds |
|---|---|---|---|---|---|
| `Forecasts_Hour` | yes, offshore / onshore / solar | 1 h | 2019-10-31 → d+1 | updated every 5 min; one row per hour, overwritten. vintages are the *columns*: `ForecastDayAhead`, `ForecastIntraday`, `Forecast5Hour`, `Forecast1Hour`, `ForecastCurrent`; `TimestampUTC` = last update | the da / id / 1 h forecast error that drives imbalance. first choice |
| `Forecasts_5Min` | same | 5 min | 2019-10-10 → d+1 | same, no `ForecastIntraday` | finer version of the above, inside the isp |
| `RegulatingBalancePowerdata` (discontinued) | yes | 1 h | `mFRRUpActBal`/`DownActBal` 2010-01-01 → 2025-03-04 11:00; **`ImbalanceMWh` and `ImbalancePriceEUR` 2022-11-01 23:00 → 2025-03-04 11:00** (20,422 h) | static archive | 2.3 years of hourly dk1 imbalance volume before the current target starts. different market design (hourly, pre-mfrr-eam). `ImbalanceMWh` correlates only 0.13 with net mfrr (up − down) and its mean is −83 mwh; meaning/sign must be checked before use |
| `RealtimeMarket` (discontinued) | yes | 1 h | 1999-07-01 → 2022-11-12 | static | regulating power up/down volumes and prices, long prior |
| `CountertradeIntraday_v2` | dk1 only | 15 min | 2025-10-14 22:00 → d+1 | `Version` + `PublicationDate` columns, i.e. vintages kept; rows exist a day ahead | tso countertrade bought in intraday; moves id price and flows |
| `AfrrEnergyActivation` | yes | 1 s | 2026-07-28 → now (looks like a rolling ~3 months) | updated every 6 h | afrr per second; after the isp only |
| `AfrrPicassoCorrections` | yes | 1 s | – | 6 h | picasso corrections and prices; after the isp |
| `GenerationProdTypeExchange` | yes | 1 h | 2015-01-01 | `Version` column | settled production by type; truth for forecast errors |
| `ElectricityProdex5MinRealtime` | yes | 5 min | 2015-01-01 | near real time | actual wind/solar/exchanges for the error target |
| `PowerSystemRightNow` | dk total + dk1 exchanges | 1 min | 2018-10-31 | near real time | as now |
| `InertiaNordicSyncharea` | dk2 only | 1 h | – | daily | not dk1 (dk1 is continental europe synchronous) |

**publication lag, measured:** at 18:46 utc `ImbalancePrice` already had dk1 `DominatingDirection` for the 18:15 isp (ended 18:30, price still null) and the full row for 18:00. so first print is ~15–30 min after isp end, not the 2 h in `backfill.md` — correct the nominal lag there.

**rate limit:** i got `429, try again in 300 seconds` after ~20 calls in a few minutes. the limit seems per ip and is shared with the archive cron on this machine. bulk pulls (`limit=0`, one call per dataset and year) are the only sane way; the full 2010–2025 dk1 `RegulatingBalancePowerdata` came back as one 55 mb response.

## nord pool (dataportal-api.nordpoolgroup.com) – free to call, terms not open

unauthenticated json endpoints behind the data portal website. verified today:

| endpoint | dk1 | resolution | free window | adds |
|---|---|---|---|---|
| `/api/DayAheadPrices?market=DayAhead&deliveryArea=DK1&date=…` | yes | 15 min | last ~2 months (28 aug ok, 25 aug 401) | duplicate of eds `DayAheadPrices` |
| `/api/DayAheadPrices?market=SIDC_IntradayAuction1` (and `2`, `3`) | yes | 15 min | **full history from 2024-06-14** (13 jun → 204, 14 jun → 200), d+1 available | the three pan-european intraday auctions: ida1 (closes 15:00 cet d−1), ida2 (22:00 d−1), ida3 (10:00 d, delivers 12–24). the da → id step, for every isp |
| `/api/IntradayMarketStatistics?deliveryArea=DK1&date=…` | yes | 96 qh + 24 ph contracts | **rolling 7 days** (21 oct ok, 20 oct 401) | continuous id per contract: open/high/low/close, vwap, `averagePriceLast1H`/`Last3H`, buy/sell volume, open/close trade times. updates live (update time 18:33 for today) |

- **auth:** none for the above; everything older → 401.
- **licence:** nord pool data is proprietary. the portal's terms allow viewing; systematic download, storage and redistribution need a data licence (paid). treat as **"republish raw? no"**, research use only, and confirm with nord pool before relying on it. verify the terms text yourself; i didn't read it today.
- **rate limit:** after ~200 calls at 0.7 s spacing the api returned **403 for every request**. i stopped there and didn't try to get around it. a polite archive is one call per day per market.
- **vintages:** auction results are final once published (`version` field). id statistics are a moving snapshot until the contract closes; archive daily or lose them after 7 days.
- jacobazu's readme says "intraday prices aren't public": the ida prices are, at least on this api.

## eSett open data (api.opendata.esett.com) – verified

openapi at `/openapi.json`. no key, no visible rate limit (a month of dk1 prices returned in 0.3 s).

| endpoint | zones | resolution | history (verified) | lag | adds |
|---|---|---|---|---|---|
| `/EXP14/Prices` (single price) | dk1, dk2, fi, no1–5, se1–4 | 15 min (dk1 quarters differ only from 19 mar 2025) | dk1 from **2021-11-01 00:00 cet** | ~1 h; later isps return **0.0 in every column** (unpublished, not zero) | imbalance, up-reg, down-reg, afrr up/down prices and `mainDirRegPowerPerMBA` (direction) for dk1 back to nov 2021 — 3.3 years more direction history than eds |
| `/EXP13/ImbalancePowerVolume` | **fi, no1–5 only** (no dk, no se) | 15 min | 2022-01-01 (hourly then), quarters by 2025 | **~13 days**: last row 15 oct 17:30 on 28 oct | neighbour imbalance; weak (no2 −0.10) and too late for a live feature, ok as lagged context |
| `/EXP09` two-price volumes | fi, no | – | – | – | pre-2021 |
| `/EXP15`, `/EXP16` | all incl. dk1 | – | – | settlement lag | consumption and production per mba |

- **licence:** eSett terms of use (opendata.esett.com/terms); i didn't read them in full. assume attribution required, check commercial use.
- **leakage:** the 0.0 placeholder rows look like real prices. drop rows where every price column is 0.0 (nordic-balancing does the same).

## entso-e transparency – not verified (no token)

`web-api.tp.entsoe.eu/api` returned 401 without a token. token is free: register on transparency.entsoe.eu, then email transparency@entsoe.eu asking for restful api access. limit 400 requests/min per token.

dk1 series worth asking for once there's a token (from the api guide, unverified for dk1 depth): 17.1.g imbalance prices (`A85`), 17.1.h total imbalance volumes (`A86`), 17.1.e activated balancing energy (`A83`), 14.1.d wind/solar forecasts da / intraday / current (`A69` with `processType A01/A40/A18`), 16.1 actual generation (`A75`), 12.1.b scheduled exchanges + 12.1.g physical flows, 13.1.b countertrading. for dk1 most of this is energinet's own data republished, so mainly a cross-check; nordic-balancing found entso-e missing 7,361 zone-quarters of 2025 that eSett has. the one thing it adds is **scheduled vs physical flows on dk1–de/nl/no/se**, i.e. the flow deviation, plus the german side (`10Y1001A1001A82H`) imbalance, which matters because dk1 sits in continental europe. licence: entso-e terms, reuse allowed with attribution for most data; check per dataset.

## fingrid, statnett, svk

| source | auth | dk1 | what it has | verdict |
|---|---|---|---|---|
| fingrid open data (`data.fingrid.fi/api`) | free key (developer-data.fingrid.fi); 401 without | no | fi imbalance, mfrr, frequency, 3-min data, cc by 4.0 | fi is barely correlated with dk1 (−0.01). skip |
| statnett driftsdata (`driftsdata.statnett.no/restapi`) | none | flows only | nordic frequency per second (last hour only, no archive), physical flows incl. dk1–no/se/de/nl | nordic frequency is irrelevant to dk1 physically (dk1 is ce synchronous). flows duplicate eds. skip |
| svenska kraftnät (mimer) | none | no | se mfrr/afrr capacity and activations | covered by nordic-balancing; low priority |

## weather

| source | auth | licence | past forecast runs? | history (verified) | lag | note |
|---|---|---|---|---|---|---|
| open-meteo previous-runs api (`previous-runs-api.open-meteo.com`) | none | api free for **non-commercial** only; data cc by 4.0; commercial = paid plan | yes: `<var>_previous_dayN` = forecast made n days earlier | dmi harmonie `previous_day1` from ~jul 2024 (jun 2024 empty); `previous_day2` empty for dmi (horizon too short); ecmwf ifs 0.25° from ~may 2024; icon-d2 ok in 2025 | ~hours | the honest as-of weather feature. what jacobazu uses (`wind_speed_100m_previous_day2`, best-match model) |
| open-meteo historical-forecast api | none | same | **no**: stitched from the first hours of each run, close to an analysis | dmi from ~jul 2024 | | leakage risk if used as a "forecast" |
| open-meteo era5 (`archive-api`) / copernicus cds | none / free cds key | cc by 4.0 / copernicus licence (commercial ok) | no, reanalysis | 1940 → | ~5–6 days (last value 22 oct 23:00 on 28 oct) | truth, not forecast. only for `era5_*` columns |
| dmi edr (`opendataapi.dmi.dk/v1/forecastedr`) | none | cc by 4.0 | no, latest run only | – | live | first call 429 "server is busy", second call ok (3.6 kb, harmonie dini 100 m wind, 15:00 utc → +2.5 days). so the 429 is load, not a ban; retry with backoff works. collections: `harmonie_dini_sf`, `harmonie_dini_eps_*` (ensemble means/percentiles), `harmonie_ig_*` |

## what others use

- **pypi `nordic-balancing` 0.4.0** (github razikale365): eSett (no key), energi data service, fingrid (key), svk, entso-e (key). prices and reserve capacity only; "not covered yet: activated balancing energy volumes". useful findings: eSett 0.0 = unpublished; eds reads query times as danish local unless `timezone=UTC`; quarters within an hour were identical in eSett until 19 mar 2025. could be used as a client, but it's beta and adds a dependency for what are three plain http apis.
- **jacobazu/dk1-imbalance-forecasting** (r, active today): eds `ImbalancePrice`, `PowerSystemRightNow` (wind, solar, exchanges per border), `Forecasts_Hour`, `DayAheadPrices`; open-meteo previous-runs at six dk1 points (100 m wind, shortwave, made 48 h ahead). no intraday prices.
- **siddiqov/dk-power-imbalance-trading** (python): eds `DayAheadPrices`/`Elspotprices`, `ImbalancePrice`, `ElectricityBalanceNonv`, `Forecasts_Hour`, `AfrrEnergyActivation`, `MfrrEnergyActivationMarket`. nothing outside eds.

nobody uses the ida prices or the legacy eds imbalance archive.

## paid, for the record (not dependencies)

nord pool data licence / api (historical intraday trades and order book, ida results with volumes), epex spot data, montel / energy quantified / volue insight (forecasts and id data), meteomatics / dtn weather, open-meteo commercial plan.

## leakage – values known only after the isp

| series | when it's known | safe use |
|---|---|---|
| `Forecasts_Hour.ForecastCurrent` (and `_5Min`) | for past hours it's the last nowcast, ~at delivery | never as a feature for the same isp; ok as the "actual" in an error target |
| `ImbalancePrice` row of the isp itself | direction ~15 min after isp end, price ~30 min | lagged only (t−2 isps and earlier for a 15-min call) |
| eSett `EXP14` | ~1 h after; before that **0.0 placeholders** | drop all-zero rows; lag ≥ 1 h |
| eSett `EXP13` neighbour volumes | ~13 days | only as long-lag context |
| `MfrrEnergyActivationMarket`, `AfrrEnergyActivation`, `AfrrPicassoCorrections` | after the isp (6 h batches for afrr) | lagged only |
| nord pool id statistics (vwap, close, volume) | final only at gate closure (contract close ~1 h before delivery for cross-border); live snapshot before | only stats of contracts already closed at the as-of time, or the live snapshot archived with its pull time |
| nord pool ida1/2/3 | ida1 ~15:20 cet d−1, ida2 ~22:20 d−1, ida3 ~10:20 d | fine after those times; not for a call made before the auction |
| `RegulatingBalancePowerdata.ImbalanceMWh` | historic, settled | target/pretraining only |
| `CountertradeIntraday_v2` | versions over time | use the version whose `PublicationDate` ≤ as-of |
| open-meteo historical-forecast api, era5 | stitched analysis / reanalysis | not as a forecast feature; previous-runs api instead |
| `GenerationProdTypeExchange` | settlement, days to weeks | truth only |

## ranked recommendation

1. **eds `Forecasts_Hour` + `Forecasts_5Min`** — free, same licence and client as now, 7 years, and the lead-time columns are built-in vintages. `Forecast1Hour` error is the strongest correlate found (−0.20). add the da / 5 h / 1 h errors per type, with `ProdEx` as the actual.
2. **nord pool ida1/2/3 dk1 prices (+ id statistics archived daily)** — the only free source of the da → id step itself, 15 min from jun 2024, available before the isp. caveats: terms need checking, no republishing, 403 after bursts, id stats vanish after 7 days so start archiving now.
3. **eSett `EXP14` dk1** — imbalance, up/down prices and direction back to nov 2021 (eds starts mar 2025). gives the direction model 3+ more years (hourly until mar 2025, so keep the regime flag). drop 0.0 placeholders.
4. **eds `RegulatingBalancePowerdata`** — hourly dk1 `ImbalanceMWh` nov 2022 – mar 2025 and mfrr activations from 2010, one bulk call. for pretraining / priors only, after the sign check; different market design.
5. **open-meteo previous-runs (dmi harmonie day-1, ecmwf)** at the six points — as-of weather from mid-2024. non-commercial only; keep era5 separate. dmi edr for the live run (backoff works).

next after these: entso-e once a token arrives (flow deviations, german imbalance); eSett neighbour volumes only as lagged context.
