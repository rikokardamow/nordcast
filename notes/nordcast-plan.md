# nordcast – plan

28 oct 2026. supersedes the scope in dk-trading-lab.md §1 and the build order in the earlier prompt. what's below is what gets built, in what order, with the gate that unlocks the next piece. the other notes (backfill, replay, risk-trading-layers, stack-web-rust) are the design for later phases; they don't get built until their gate opens.

## the call, precisely

- **target:** dk1 system imbalance (mw, energinet's real-time signal in `PowerSystemRightNow`), mean over each 15-min isp.
- **two parts per call:** (1) dominating direction of the isp: up / down / none, as a calibrated 3-class probability; (2) volume, as q10 / q50 / q90. since 2 jun 2025 energinet ignores mfrr needs under 25 mw, so ~1 in 10 dk1 isps has no direction and settles at day-ahead; a single regression would be wrong ~10 % of the time by construction.
- **horizons:** 15, 30, 60 min before isp start. frozen at isp start − h − 1 min.
- **scored against:** the first 5-min print covering the isp (volume) and the first `ImbalancePrice.DominatingDirection` (direction). both kept as vintages; later revisions scored separately, never overwrite.
- **who it's for:** the 60-min call is the last one that can still be traded (nord pool idc closes 60 min before delivery). the 15/30-min calls are for the hold-into-imbalance decision and for balancing bids. the scorecard says this on the page.

## phases and gates

### phase 0 – archive (this week, ~4 h) – starts before anything else

the history I need later can't be bought: energinet's first prints, the 7-day `mfrrRequest` window, dmi's 24–48 h of forecasts. so before the model exists:

- a launchd job on the mac mini (`StartInterval 60`, same pattern as energy-forecasting's `ops/`) pulling `PowerSystemRightNow` dk1+dk2 and `mfrrRequest` every minute, `ImbalancePrice` every 15 min, and every dmi harmonie dini run (stac grib, six coastal points + the jutland box) to append-only daily parquet partitions with `pulled_at_utc`, pushed hourly to a private archive repo. not github actions: actions cron starts late too often for a 5-min feed.
- the sign-convention check, before any model code (below).

### phase 1 – the record (weeks 1–6, ~60 h)

| week | work | output | hours |
|---|---|---|---|
| 1 | scaffold from energy-forecasting (copy, rename), the schema migration from from-energy-forecasting.md (timestamptz, horizon, direction, `history_asof`), isp calendar with dst tests | tests green, release table loaded | 8 |
| 2 | sources: energinet (eds + real-time), dmi, esett as the second price source; backfill from inception with estimated vintages; data register filled | row counts per series, notes/inception.md | 12 |
| 3 | baselines (persistence, persistence-ar1, climatological direction by hour); **start freezing persistence live** so the record's clock starts; first chart | 01 notebook chart, scorecard v0, persistence live | 10 |
| 4 | features with the no-leakage test; lightgbm volume (quantile) + lightgbm direction (multiclass, calibrated); mapie on volume | 03 notebook, scorecard rows | 12 |
| 5 | replay rounds 1–4 on the clean window (from 1 oct 2025), reviews edited by me | replay-log.md v1 | 10 |
| 6 | lightgbm frozen beside persistence as a challenger; score job; daily stamp; heartbeat + deadman; 7-day soak; pre-registration committed | live, readme with scorecard | 8 |

the headline call stays persistence until lightgbm beats it over the pre-registered window (the challenger's first 60 full days, 15-min horizon, pinball loss on volume and brier on direction, bootstrap 90 % interval excluding zero) and passes the independent validation review. swaps only at a quarter boundary, as in energy-forecasting's rules: with the challenger live from ~early december, the earliest promotion is 1 apr 2027. the model earns the call; I don't give it.

**gate g1:** 30 consecutive days with on-time freeze rate ≥ 99 % and no unresolved incident.

### phase 2 – value (after g1, ~25 h)

- L1 position + L2 pnl notebooks from risk-trading-layers.md, on the hold-into-imbalance translation (10 mw left open in the direction call, settled at `ImbalancePrice`), with persistence as the control.
- the council (chronos-2, timesfm 2.5, timestral) as zero-shot challengers. none blocks a freeze; pretraining cutoffs written in each model card, and any backtest window that overlaps a model's pretraining is flagged (arxiv 2609.20554 shows that leakage distorts tsfm backtests).
- first linkedin post with the live chart and the scorecard.

**gate g2:** 90 days live, lightgbm (or a challenger) promoted or explicitly not, validation note written.

### phase 3 – book and risk (after g2, ~30 h)

- L3 risk: limits written before any position, var on the strategy pnl with kupiec/christoffersen, stress on 4 mar 2025 and storm week oct 2026.
- L4: the 100 mw wind-park book; €/mwh imbalance cost saved by re-nominating on the 60-min call, net of an execution cost assumption.

### phase 4 – rust book and site (q2 2027 at the earliest)

per stack-web-rust.md, only if phases 1–3 are live and boring. the book stays "simulated, german/dutch-calibrated" (no dk1 calibration exists; nord pool order data is paid). mari accession (target q1 2027 when this was written; now no firm date, sep–oct 2027 likely, notes/mari-plan.md) is a regime break that comes first: retrain, re-validate, note it in the record.

## the sign-convention check (phase 0, ~2 h)

the column name and sign of energinet's real-time imbalance weren't readable from here. don't trust a description; test it:

1. read `/meta/dataset/PowerSystemRightNow` and energinet's real-time imbalance q&a in a browser; write the column names, unit and stated sign into notes/sources.md.
2. on the overlap since 4 mar 2025, compare the 15-min mean of the imbalance signal with `ImbalancePrice.DominatingDirection` and with mfrr activated up/down. if the system is short (deficit), energinet activates up-regulation and the dominating direction is up. the sign that lines up with that in > 90 % of directional isps is the convention; write the hit rate down.
3. a test in the repo asserts it on a fixed week, so a silent change at energinet breaks ci instead of the record.

## prior art (say so in the readme)

- `jacobazu/dk1-imbalance-forecasting` – backtests dk1 quarter-hour imbalance spreads.
- `siddiqov/dk-power-imbalance-trading` – catboost on dk1/dk2 imbalance prices with a backtest.
- `nordic-balancing` (pypi) – typed clients for esett / energinet / fingrid imbalance prices; use it as the cross-check source, not a dependency of the record.

what nordcast adds that they don't: frozen, hashed, timestamped calls scored against the first print; the direction class; the replay log; published intervals. that's the line in the readme.

## what I'm not building in v1

the rust book, the site, wasm, the battery, the idc execution sim, dk2. all designed, all parked with a gate.
