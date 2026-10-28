# replay – the five-year rehearsal

28 oct 2026. before the live record starts I want to have "done this before". so the repo replays the forecasting process over the backfilled history as if I had started five years ago and kept the same discipline the whole way: pick a method, analyse, forecast, validate, review, adjust, go again. the output is a dated log of errors and what I changed, and a model ladder that earned its place quarter by quarter rather than being chosen because it's fashionable now.

## what the replay is and isn't

- it's a walk-forward simulation on estimated vintages. every quarter of history is a "round". at the start of a round the model only sees data stamped before the round, forecasts the whole round isp by isp at each horizon, gets scored, and then a review is written from that scorecard alone.
- it isn't a record. nothing from the replay is frozen, stamped or shown as a call. the scorecard columns are labelled `replay` and sit beside `live` and never get averaged with it.
- the point is the process, not the number. the thing I want at the end is a `notes/replay-log.md` where every round has: the method used, the error it made, what I'd have noticed, what changed for the next round. that log is what I'll have when a desk asks "how do you handle a model going wrong".

## the ladder

methods are tried in this order, and a method is only promoted to "the model" for the next round if it beat the incumbent on the previous round's scorecard. no skipping. no promoting on the same round it was introduced. the ladder is the one every forecasting course teaches and the one the desks actually walk:

1. persistence (round 1 is persistence only; the point is to see how hard it is to beat)
2. persistence + mean reversion (ar(1) on the imbalance)
3. seasonal naive: same isp yesterday, same isp last week
4. linear regression on lags + calendar
5. arima / sarima on the 15-min series (statsmodels), one order chosen by aic on the first round it appears, then fixed
6. regression with exogenous: wind forecast error, da price, exchange ramps
7. gradient boosting (lightgbm) on the same features
8. quantile versions of whichever won (quantile regression, then lightgbm quantile, then mapie conformal)
9. the council (timestral, chronos-2, timesfm) zero-shot as challengers
10. ensembles only if two methods are within noise of each other for two rounds

each rung gets introduced at a round boundary and has to win a round to be the model. if it doesn't win, it stays as a challenger for one more round, then gets dropped and logged.

## each round, in order

1. **analyse**: on the training window only. acf/pacf, hour-of-day and weekday profile, the distribution of the target (tails, sign asymmetry), a stationarity check, correlation of the target with each candidate feature. one notebook cell per item, one chart each, saved under `replay/<round>/analysis/`.
2. **choose**: the method for this round per the ladder rules and the previous review. written down before forecasting, in `replay/<round>/plan.md`, with the exact config.
3. **forecast**: walk-forward through the round, refitting weekly, each horizon, point and q10/q90 where the method has them. same `(read, series_id, isp, asof)` signature as the live model so nothing changes between replay and live.
4. **validate**: the full scorecard (mae, rmse, sign, pinball, coverage, 10 mw pnl) vs persistence and vs the incumbent. plus the diagnostics the course teaches and the desk uses: error by hour of day, error by wind-forecast-error bucket, residual acf (is there structure left), biggest ten misses with what the feed looked like at the time.
5. **review**: `replay/<round>/review.md`, written from the scorecard and diagnostics only, no peeking at the next round. headings: what was wrong, where (hours, regimes, horizons), why I think so, what changes next round, what I'm not changing and why. two hundred words, in my voice.
6. **adjust**: the change goes into the next round's plan. one change per round so I can attribute it.

claude code writes the review drafts from the numbers; I edit them. the drafts have to be specific ("mae 38 mw worse than persistence in the 05:00–07:00 ramp on days when fc_wind_dayahead was off by more than 300 mw") not generic ("the model struggled with volatility").

## rounds

quarterly from the earliest quarter where the target exists (expect q2 2024 for the imbalance volume, q1 2025 for anything using the imbalance price, and only ~4 clean quarters since the 1 oct 2025 15-min switch; earlier for the wind and price series, so run a wind-production replay from ~2019 on the same ladder if I want the five-year span, and say in the log that the imbalance replay is shorter because the data is). ~10 rounds for imbalance, ~28 for wind. that is the "five years".

## what comes out

- `notes/replay-log.md`: one section per round, the review, the config, the scorecard line. the document I'd hand to an interviewer.
- `replay/scorecard.csv`: every round × method × horizon.
- the live model's starting config is the last round's winner, and the live pre-registration says so.
- a chart: scorecard mae by round, persistence as a flat line, each rung entering when it did. that's the linkedin post.

## guardrails

- the training window is cut by `value_asof` at the round start; the test is the existing no-leakage assertion, run per round.
- hyperparameters are chosen inside the training window (last 20 % of it as validation), never on the round being scored.
- the ladder order and the promotion rule are in this file and committed before round 1 runs. if I change them mid-replay, the log says so and why.
- estimated vintages flatter everything a little. the log says so once at the top and never again.
