# web and rust – nordcast and gasbook

28 oct 2026. two additions to both repos: a next.js + react front end, and a rust core for the parts where python is too slow or too loose. same rule as every layer: it reads the record, it never writes to it, and it ships only after the layer under it has a scored number.

## why rust, and only where

python stays the language of the record: pulls, value_asof, freeze, score, the replay, the notebooks. rust goes in for three things where speed or exactness is the point:

1. **order book.** a limit order book with price-time priority, a matching engine, and an order-flow generator. python is fine for a toy book; it's not fine for replaying a day of 15-min products with hawkes arrivals and running ten thousand execution paths for the cost frontier. this is the honest replacement for the paid epex / ice book I don't have.
2. **monte carlo and dynamic programming.** gas storage valuation by least-squares monte carlo (boogert–de jong) and the rolling intrinsic lp re-solved daily over years; the battery and wind-park books in nordcast re-solved every isp. tight loops, lots of paths.
3. **the hot path of the live job.** feature building for 96 isps × 3 horizons every 15 minutes is fine in python today. if the actions run goes past ~2 minutes, the feature builder moves to rust. not before.

everything is a crate with a pyo3 binding built by maturin, so python calls it like any module and the notebooks don't change. one crate per repo, a workspace if it grows. tests in rust (`cargo test`) and the same tests mirrored in pytest against the binding, so the python side proves the binding returns what the rust side does.

## nordcast: `nordbook` crate

```
rust/nordbook/
  Cargo.toml          pyo3, rand, rand_distr, serde, criterion (bench)
  pyproject.toml      maturin, module name nordcast._nordbook
  src/
    lib.rs            pyo3 module
    book.rs           OrderBook: bids/asks as BTreeMap<Price, VecDeque<Order>>, price-time priority
    order.rs          Order {id, side, price, qty, ts, owner}, OrderType {Limit, Market, IOC, FOK, Iceberg}
    matching.rs       match_order(book, order) -> Vec<Fill>, cancel, amend (amend loses priority unless qty down)
    product.rs        Product {delivery_start, delivery_end, gate_closure} for dk1 15-min, 30-min, hourly, blocks
    hawkes.rs         multivariate hawkes simulator (ogata thinning): buy/sell × aggressive/passive, cross-product excitation
    flow.rs           order-flow generator: hawkes arrivals + price placement from a stated distribution around mid
    execution.rs      parent order slicing: twap, vwap-proxy, almgren-chriss, hawkes-aware schedule
    impact.rs         transient impact kernel (propagator), permanent vs temporary split
    replay.rs         replay a day: products open/close on the dk1 idc calendar, mid follows the imbalance price path
  benches/book.rs     1m orders/s target on the mac mini
  tests/              price-time priority, partial fills, iceberg refresh, cancel of resting, gate closure rejects
```

what it's calibrated to, and what it isn't: there's no free dk1 idc book (nord pool sells delayed trades from €750/yr and order books at €3.7–4.4k per country, with academic terms; order-book lifecycle history only from 11 mar 2025). the amsterdam hawkes paper (2504.10282) calibrates on german hourly products (branching ratio 0.28–0.36, half-life 1.2–2.2 s); the wageningen cross-product hawkes paper (2610.23619, dutch epex 2024) gives the cross-excitation (quarter-hours lead hours, ratio 2.8 calm / 1.5 stress); the kit/oxford bess-on-idc paper (2610.02830) gives the liquidity profile into gate closure. I use their published parameters, scale liquidity down by a stated factor for dk1, and label every chart "simulated book, german-calibrated". the mid price path comes from my own record (the da price and the imbalance price), so the book sits on real dk1 prices with fake depth.

what nordcast uses it for:
- L4 book: the wind park re-nominating intraday on the 60-min call has to trade the forecast error into the book. execution cost goes into the imbalance-cost-saved number, so the €/mwh is net of slippage, not gross.
- the idc execution project (dk-trading-lab #5) becomes this crate plus one notebook: the cost frontier for a 50 mw revision, twap vs almgren-chriss vs hawkes-aware.
- the battery book (#3): rolling intrinsic trades into the book instead of at a clean price.

## gasbook: `gasbook-core` crate

```
rust/gasbook-core/
  Cargo.toml          pyo3, nalgebra, rand, rand_distr, rayon, serde, criterion
  pyproject.toml      maturin, module name gasbook._core
  src/
    lib.rs
    curve.rs          forward curve, contract calendar (nymex ng, ice endex ttf), roll rule 5 bd before expiry
    two_factor.rs     schwartz–smith simulation and kalman fit on contracts 1–4
    storage/
      facility.rs     Facility {capacity, inj_rate, wd_rate, ratchets, inj_cost, wd_cost}
      intrinsic.rs    rolling intrinsic: lp on the curve via a small simplex or dp on a volume grid
      lsm.rs          least-squares monte carlo (boogert–de jong), rayon over paths, basis = laguerre
    options.rs        black76, bachelier, calendar spread option (kirk, bachelier for cso), greeks
    book.rs           OrderBook for futures + calendar spreads, implied-in/implied-out spread matching
    matching.rs       outright and spread legs, cme-style implied prices
    risk.rs           historical and filtered-hs var on a book, fast path for the gasbook L3 stress grid
  benches/
  tests/              lsm value ≥ intrinsic, ≤ intrinsic + extrinsic upper bound on a known case; put–call parity; implied spread price consistency
```

the order book here is about calendar spreads, because that's where gas trades: a winter–summer spread order on nymex is matched against outrights through implied prices, and that implied-matching logic is the thing a gas desk would ask about. it's a model of the mechanism, not a replay of real flow; the depth is stated, the prices come from the licensed curve source (eia stopped contracts 1–4 after 5 apr 2024), and it's labelled. implied rules from cme/ice docs: real orders fill before implied at the same price; implied bids never trade against implied offers; cme publishes a 2-deep implied book; ice ttf builds second-generation implieds across months/quarters/seasons/cals but broadcasts the front 3 months. still to check by hand: cme leg pricing on a spread fill, fifo vs pro-rata for ng, ng spread tick (nymex rulebook ch. 220).

what gasbook uses it for:
- L4 storage valuation: lsm extrinsic on top of the intrinsic, daily, years of history. python would take hours; rust with rayon takes minutes.
- the winter premium series: schwartz–smith fit and simulation for the premium distribution.
- L4 hedge book: rolling the winter strip through the spread book, so roll cost is a matching outcome, not an assumption.
- L3 stress grid: thousands of scenarios on the book in under a second, so the stress page can be interactive.

## next.js + react, both repos

pattern copied from energy-forecasting's `site/`: next.js on vercel, app router, reads supabase live through a read-only role with row-level security, revalidates when the score job finishes, design tokens in `styles/tokens.css`, charts read colours from the tokens via `lib/chartTheme.ts`, light and dark both. same components where they fit (`ForecastCard`, `ScoreTable`, `ScoreSummary`, `StateBadge`, `Countdown`, `FreshnessDot`, `TimeSeriesChart`, `Unavailable`), same tests (vitest, a11y script).

additions for these two:

- **echarts for the record pages** (already the energy-forecasting choice), **plotly.js** only where the notebook already made the figure and the page just embeds its json.
- **the order book page** is the one that needs react proper: a depth ladder, trade tape, and an execution replay scrubber. rust compiled to **wasm** (`wasm-pack`, the same crate behind a `wasm` feature flag) runs the book in the browser, so a reader can drag the urgency slider and watch the cost frontier move without a server. this is the page I'd send a desk.
- **layer pages** (`/layers/position`, `/pnl`, `/risk`, `/book`) render the committed plotly html first; a page gets built only when the layer earns it, as in risk-trading-layers.md.
- **no client-side secrets.** the anon key is the rls read-only role; restricted series never reach a view the web role can read (energy-forecasting's `licence_class` check).

nordcast pages:
```
/                 latest nowcast card per horizon, live countdown to the next isp, record line
/isp/[ts]         one isp: the three frozen calls, the bands, the first print, the error vs persistence
/scorecard        every scored isp, filterable by horizon/hour, misses shown
/data/dk1         imbalance, afrr/mfrr, wind minus forecast, the 5-min feed with freshness
/replay           the replay log: mae by round, each rung entering, the reviews
/book             wasm order book: depth ladder, tape, execution scrubber (simulated, labelled)
/layers/...       position, pnl, risk, wind-park book
/methodology      how freeze and score work, how to verify a hash
```

gasbook pages:
```
/                 three series cards, next eia release countdown, record line
/storage/[week]   the weekly call vs consensus vs 5-yr, the print
/premium          hh winter contracts with the frozen premium calls marked on the curve history
/eu-path          fill path vs 5-yr vs frozen calls, country small multiples from agsi+
/curve            hh contracts 1–4 history, theory-of-storage chart (spread vs inventory deviation)
/storage-value    intrinsic and lsm value over time for the synthetic facility
/book             spread order book with implied matching (wasm), the roll replay
/layers/...       position, pnl, risk, hedge book
/methodology
```

## build order, per repo

1. record live and scored (the existing prompt steps). no web, no rust before this.
2. rust crate scaffold with the book and one benchmark; pyo3 binding; mirrored tests. one weekend.
3. the notebook that uses it (nordcast: execution frontier; gasbook: lsm storage value). one weekend.
4. next.js site: copy energy-forecasting's site, point it at the new supabase, build the record pages first (`/`, the per-call page, `/scorecard`, `/methodology`). one weekend.
5. wasm build of the crate and the `/book` page. one weekend.
6. layer pages as layers earn them.

## tooling

- rust stable, `cargo`, `maturin develop` for the binding, `wasm-pack build --target web` for the browser.
- ci: `cargo fmt --check`, `cargo clippy -- -D warnings`, `cargo test`, `maturin build`, then pytest, then the site's vitest and a11y. one workflow per language, all on push.
- node via pnpm (energy-forecasting's lock), next 16 (turbopack by default, ignores `webpack()` config, so no `asyncWebAssembly` recipe), react 19, typescript strict. load the wasm only in a `'use client'` component with `init()` on mount, from `wasm-pack build --target web`; test in both `next dev` and `next build`.
- versions checked 28 oct 2026: pyo3 0.30, maturin 1.15, wasm-bindgen 0.2.129 (now under the `wasm-bindgen` github org; rustwasm was archived sep 2025), wasm-pack 0.15, criterion 0.8. reference projects: nautilustrader's rust core (pyo3 behind a feature flag), orderbook-rs; the c++ simulator in 2510.08085 for the book-vs-flow separation; 2410.06839 (edf) for a fully specified sparse intraday book.
- the mac mini builds wasm fine; vercel builds the site, not the wasm (commit the built wasm under `site/public/wasm/` with its hash in a manifest, rebuilt in ci).

## not doing

- no rust in the freeze/score path. the record's code stays boring python that's already tested.
- no live order entry, ever. the book is a model of a market I can't see.
- no real order-book data scraped from anywhere. if I ever pay for epex or ice depth, the replay module takes it as input and the "simulated" label comes off.
