# literature – what the papers say about this call

29 oct 2026. academic prior art for nordcast, beside the three github repos in the readme. found and read through alphaxiv today; every number below is from the paper named, not from me. nothing here changes the record; it's what to compare against and what to argue in the validation note.

## the short version

- **nobody publishes what nordcast calls.** the literature forecasts the imbalance *price*; only a handful forecast the imbalance *volume*, and none i found make a calibrated 3-class *direction* call scored against a tso's first print. the nordic papers are price models from 2007–2023 at 1–48 h horizons. the readme line ("what nordcast adds") holds up.
- **metrics and baselines match the field.** pinball loss / crps on quantiles, coverage of the interval, persistence as the naive floor. nordcast's pinball + brier + coverage is the standard set; a diebold–mariano test or a block bootstrap (we use the bootstrap) is how differences get called significant.
- **the inputs the field calls underused are the ones nordcast already has or plans:** per-minute tso data (`PowerSystemRightNow`), intraday market data (nord pool ida + id statistics, data-alternatives.md #2), cross-border flows.
- **one tension for the pre-registration:** the review says a test set should span at least a year to avoid seasonal effects. the pre-registered window is the challenger's first 60 days. that's fine for a *promotion* rule with a bootstrap interval, but the validation note should say a 60-day win isn't a seasonal claim.

## papers

### verstraeten, mascarenhas, kazmi – a review of imbalance price forecasting in europe (arxiv 2605.17054, may 2026, ku leuven)

the current survey. table ii lists 20 papers, 2007–2025.

- **nordic entries:** olsson & söder 2007 (sarima + markov, 24 h), jaehnert 2009 (48 h), brolin & söder 2010 (armax, 24 h), klæboe 2013 (arma + markov, 1 h and 36 h, the only early one with probabilistic output: mae + unconditional coverage), jónsson, pinson et al. 2014 (holt–winters, 36 h; dtu), dimoulkas 2016 (hmm, 1 h / 36 h), backe et al. 2023 (lstm on nordic balancing *prices and volumes*, 10 h, rmse only). finland: makrides 2024 (random forest, 1 h). no dk1-specific paper, none at 15–60 min.
- **two approaches:** (1) predict the system imbalance / regime first, then the price (fundamental); (2) predict the price directly with ml. nordcast is approach 1 stopped at step one – the direction and volume are the product.
- **horizons have shrunk** from a day to 15 min – a few hours; lookback 2–2.5 h was optimal where tested (bottieau 2022, ganesh & bunn 2023).
- **recalibration:** no consensus. under two months of test, nobody recalibrates; over a year, daily (narajewski 2022, dol 2025), monthly (dumas 2019) or never (bottieau 2022, backe 2023).
- **calibration window:** "at least one year" of training is the norm. nordcast's clean window starts 1 oct 2025, so lightgbm v1 is at the bottom of that range – worth one line in the model card.
- **naive baselines:** persistence, and the da or id price as an imbalance-price forecast. the second doesn't translate to a volume target; persistence and ar(1) are the right floors for us.
- **gaps they name:** tso renewables forecasts are often inaccurate (kazmi & tao 2022 – relevant to the `Forecasts_Hour` errors in data-alternatives.md); intraday data is paywalled; per-minute tso data is unused; no common benchmark; accuracy should be judged with downstream value (battery or trading case), which is phase 2's l1/l2 notebooks.

### bui, mascarenhas, kazmi, verstraeten – tsfms for da and imbalance prices in belgium (arxiv 2605.17045, may 2026)

the closest thing to a phase-2 council dry run. belgian imbalance *price*, 2-hour horizon (8 qh), test year 2023, point forecasts only (mae / rmse).

| model | mae qh1 | qh4 | qh8 |
|---|---|---|---|
| persistence | 76.8 | 104.68 | 124.57 |
| timesfm 2.5 (univariate) | 74.39 | 92.15 | 97.78 |
| chronos-2, ar | 72.91 | 90.3 | 95.43 |
| chronos-2, arx (covariates) | 70.1 | 87.73 | 93.72 |
| ml ensemble (lear + dnn, trained) | 67.19 | 87.3 | 93.96 |
| chronos-2 + ml ensemble | 67.09 | 86.45 | 92.83 |

€/mwh. what carries over:
- trained models beat zero-shot tsfms at the shortest horizon (qh1, our 15-min call) by ~4 %; chronos-2 with covariates only catches up by qh8 (2 h).
- averaging tsfms together is worse than chronos-2 alone (their forecasts are highly correlated). averaging chronos-2 with the trained models is best everywhere, but a diebold–mariano test found the da-market version of that gain not significant.
- all tsfms are worst in the 1st and 10th price deciles – the extremes are where a council member would hurt.
- they checked the test period against each model's disclosed pretraining data before running. we should do the same (council-model-cards.md).

### yu, cremer, pinson, kazempour, … bunn – from intraday orderbook to imbalance price (arxiv 2609.37903, sep 2026)

germany and austria, 2022 – jan 2025, epex orderbook (paid) + entso-e fundamentals; horizons 15, 60, 180 min; quantiles 0.1 / 0.5 / 0.9; metrics are average quantile loss and the 80 % interval coverage error – i.e. the same q10/q50/q90 setup as lightgbm_volume_v1.

- **vwap of the self product plus the next 1–12 products** was the best orderbook representation in both countries, beating ohlcv and last mid price.
- in austria the orderbook alone was enough; in germany adding fundamentals (renewables forecasts/actuals, load, da price, cross-border net positions, operational system imbalance) kept reducing loss. which way dk1 goes is an open question, and nord pool id statistics (data-alternatives.md #2) are the only free way to find out.
- a nonlinear model beat linear quantile regression in 17 of 18 cases.
- some fundamental series publish with irregular delays; the orderbook is real time. that's the same leakage point as data-alternatives.md's leakage table.
- concrete feature for later: `averagePriceLast1H` per qh contract for the target isp and the next four. only contracts that are closed or snapshotted before the freeze.

### o'connor et al. – conformal prediction for da and balancing prices (arxiv 2502.04935)

irish balancing market, 8 h; probabilistic, scored with pinball, interval width, coverage, winkler score. supports mapie / conformal on volume as planned (plan week 4).

## what i'd change in nordcast because of this

nothing in the record. three small things for later, in order:

1. **validation note (phase 2):** cite the review for metric choice, say the 60-day window is a promotion rule not a seasonal result, and report a diebold–mariano p-value beside the bootstrap interval, since that's what readers in this field look for.
2. **council (phase 2):** chronos-2 with covariates first, timesfm second; score the chronos-2 + lightgbm average as its own row, because that combination is the one that won in both tsfm papers. see notes/later/council-model-cards.md.
3. **features (after g1):** nord pool id vwap for the target and next products, once the archive has enough days.

## not checked

- the dutch (dol et al. 2025), german (narajewski 2022) and greek (plakas 2025) papers in the review's table – cited from the review, not read.
- backe et al. 2023 (nordic prices *and volumes*) – conference paper, not on arxiv; the closest prior work to nordcast's volume call and worth reading in full.
- "a market-rule-informed neural network for imbalance price forecasting" (arxiv 2605.09061) – found, not read.
