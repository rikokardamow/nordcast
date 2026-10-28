# risk and trading layers – nordcast and gasbook

28 oct 2026. how a forecast record becomes a trading record with risk on it, in layers, the same shape in both repos. most of the code exists already: supply-or-demand built and tested a trading analytics core in sep 2026 (specs 18–27, `core/systematic.py`, `core/backtest.py`, `core/strategies.py`, `core/risk.py`, `core/risk_desk.py`, `core/vol.py`, `core/journal.py`, `core/ledger.py`) and energy-forecasting's design review said to leave the old repo's storage and publishing but port the pure modules. these are the pure modules. they get copied, not imported, and they never touch the database: the record stays the record, the layers read it.

the energy-analyst skill lives in `.claude/skills/energy-analyst/` on the mac and is gitignored, so I can't see it from here. its references folder is what energy-forecasting's parking notes cite for chart conventions and the catalogue. rule for claude code: read that skill before any layer that draws a chart or names a series, and follow its conventions over mine where they differ. if the skill has risk or trading conventions I haven't written here, they win.

## the principle

a layer is added only when the layer below has a scored record. forecast before position, position before risk, risk before book. each layer is a notebook first, a job second, a page last, and it has one chart, one test and one falsifiable number. nothing in a layer edits the record below it.

```
L0  record        frozen calls, scored          (exists: the repo)
L1  position      what I'd have done with it    signal → size → position series, lagged one step
L2  pnl           what it would have made       backtest with costs, attribution, fractionation
L3  risk          what it could have lost       var/es with backtests, limits, stress, margin
L4  book          the hedge and the residual    synthetic exposure, hedge program, effectiveness
L5  journal       the human layer               every flip logged, reviewed, tied to the articles
```

## L1 position

copy `core/systematic.py` (zscore, reaction, reaction_piecewise, vol_target, blend, position, apply_guardrails) and `core/strategies.py`'s shape (a registry, `required_inputs`, `build_positions` that raises rather than returning a flat series). the signal is the record's own call, nothing else:

- **nordcast**: signal = frozen nowcast point at each horizon, z-scored against its own recent distribution; position ∈ [−1, 1] via `reaction`, sized to a stated 10 mw; direction = sign of the nowcast; a position only on isps where the q10–q90 band excludes zero (the band is the conviction filter). a second strategy: persistence as the control, so the pnl table shows what the forecast added.
- **gasbook**: three strategies, one per series. storage call → front-month hh direction into thursday (long if my call is a smaller build than consensus, flat if inside the band). winter premium → short the winter contract 90 days out when the storage-conditioned premium is above its 80th percentile, cover at expiry or at the 60-day mark if the sign flips. eu path → long ttf front-season when my fill-path call is below the 5-year path by more than the band, flat otherwise; if no ttf curve, the position is recorded and marked against the front-month only, labelled.

guardrails from `apply_guardrails` adapted: nordcast caps when the feed is stale or a dmi run is missing; gasbook caps when the eia report is shifted or the consensus capture failed.

## L2 pnl

copy `core/backtest.py` (`backtest`, `spread_to_return`, `fractionate`, `inventory_predictability_test`). its two acceptance guards carry over as the tests: a constant +1 position reproduces buy-and-hold exactly at zero cost, and shifting returns one step changes the pnl. positions are lagged one step. costs: nordcast at the imbalance price with a stated slippage in €/mwh; gasbook at settlement with 2 bps and the roll on the stated roll rule (5 business days before expiry, from `core/curve.py`).

attribution per `core/journal.py`'s split: directional, carry (roll yield for gas, nothing for nordcast), vol (options later), slippage. fractionation by the conditioners the record already stores: nordcast by hour, wind-forecast-error bucket, horizon; gasbook by storage-vs-5-year decile, hdd surprise, report-shift weeks.

the chart: cumulative pnl of the forecast strategy vs the control, with the record's scorecard mae on a second axis so a reader sees whether skill and pnl move together. the number: pnl per unit of mae improvement.

## L3 risk

copy `core/risk.py` (garch-midas-evt var/es, kupiec uc, christoffersen cc, `hs_var` as the control that fails, `compare_models`, `realised_vol`) and `core/risk_desk.py` (`exposure_tree`, `portfolio_var`, `stress`, `margin_stress`, `hedge_effectiveness`, `liquidity_check`). the lyu et al 2024 energy economics paper is the source; `specs/22_risk-engine.md` has the tests with numbers (beta weights sum to 1, evt on t(4) draws gives ξ in [0.15, 0.35], kupiec 10/1000 at 1 % ≈ 1, 25/1000 < 0.01).

- **nordcast**: var on the 15-min strategy pnl, 1 % and 5 %, garch-t and garch-evt (midas needs a monthly macro variable; for a 15-min series the long-run component is the daily wind-forecast-error variance instead, say so). limits: a daily loss limit and a per-isp position cap, written down before the first live position; a breach flattens the next isp and logs it. stress: storm week 20–26 oct 2026 replayed, the 2024 pilot's first week, a feed outage (position held through missing prints).
- **gasbook**: the full engine as specced. midas long-run component from fred industrial production (us ip as the proxy, captioned). book and margins as manual csvs (`book.csv`, `margins.csv`) per spec 22. stress scenarios in `scenarios.yaml`: feb 2021 winter storm uri (hh), mar 2022 ttf (the margining squeeze bis bulletin 59 describes), dec 2022 eu storage scare, parallel ±$1 hh, winter–summer spread ±$0.50, ttf front ±€20, hh–ttf basis ±30 %. margin stress with span-style outright and spread rates, days-to-breach against a stated credit line.

the chart: var fan with exceptions marked and the pass/fail matrix beside it, historical simulation shown failing. the number: exceptions vs expected at 1 %.

## L4 book

the hedging layer.

- **gasbook**: a synthetic gas-fired ccgt (stated heat rate, capacity, dispatch rule against a power price I can get: dk1 day-ahead from nordcast's own store, which ties the two repos together) and a synthetic supplier winter load (hdd-shaped). hedge programs: strip, seasonal, rolling 1/3-1/3-1/3, and the record-informed one (adjust the rolling program by the storage call). `hedge_effectiveness` (1 − var(hedged)/var(unhedged), rolling 60d), basis risk hh vs the physical index, shape risk when the load profile moves. `core/vol.py`'s black76 and bachelier for a collar and a three-way on the winter strip; greeks through `exposure_tree`; options data stays manual csv until there's a source. this is the deep-hedging-of-ppas paper's practical cousin and the one a desk reads.
- **nordcast**: the book is a wind park. a synthetic 100 mw dk1 park with energinet's forecast as its day-ahead nomination; the imbalance cost of its forecast error, and how much the nowcast reduces it if the park re-nominates intraday on the 60-min call. `hedge_effectiveness` on the imbalance cost. the number: €/mwh of imbalance cost saved. that's the number a wind operator or a bro pays for.

## L5 journal

copy `core/journal.py` and `core/ledger.py`. every strategy flip logs a trade with a snapshot of the conditioners at `as_of` (the test: snapshot at as_of, not latest). closed trades get a review in the same voice as the replay reviews. the kardamow ledger ties published articles to gauges (`parse_gauge`, `distance_to_trigger`, `resolve`, `score`) so the articles are scored the same way as the calls. the playbook seed from spec 27 is oil; add a gas and a power section as cases happen, no book text.

## interactive

layers are interactive in three steps, same as everything else: notebook (ipywidgets sliders for the parameters the reader would want to move: position size, cost, var quantile, hedge ratio), then a plotly html committed under `docs/layers/<layer>.html` (interactive, zero infra, linkable from a post), then a next.js page in the energy-forecasting site pattern when the layer has earned it. no streamlit; the design review retired it. every card shows estimation window, last refit, out-of-sample status vs the named benchmark, exception count, structural-break date, exactly as `00_TRADING_CONVENTIONS.md` says.

## what carries over verbatim from supply-or-demand

`core/systematic.py`, `core/backtest.py`, `core/strategies.py` (shape), `core/risk.py`, `core/risk_desk.py`, `core/vol.py`, `core/journal.py`, `core/ledger.py`, `core/curve.py` (roll rule, nearby construction), `core/theme.py` (chart primitives: var_fan_chart, pass_fail_matrix, stress_waterfall, attribution_stack_chart, calibration_curve_chart), and `specs/00_TRADING_CONVENTIONS.md`'s rules: signals at t use only rows with date ≤ t and release_date ≤ t; degenerate inputs fail loudly, never substituted; published benchmark figures shown beside the repo's own with the deviation; spreads never from a back-adjusted series.

what doesn't: the duckdb lake, the streamlit pages, the pipelines, the catalogue of oil strategies (carry 1–13 needs rank 13 and eia only has 1–4; that's recorded as a miss in spec 21 and stays one).

## order

nordcast: L1–L2 after the first scored week; L3 limits written before the first live position; L4 the wind-park book after a month of scores; L5 from the first flip.
gasbook: L1 per series as each goes live; L2–L3 after series 1 has eight weeks; L4 the hedge book is its own build (two weekends) after L3; L5 from the first flip, and the ledger from the first kardamow gas piece.

## what I'm not doing

- no live orders. ibkr is for data (the ttf and hh curves, options settlements when I pay for them), not execution. the journal says "would have".
- no position size in anything published. the layers show direction, instrument, level and the risk number; the reader decides the size, same as the articles.
- no layer without a record under it.
