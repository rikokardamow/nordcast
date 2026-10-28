# replay log

28 oct 2026. the walk-forward rehearsal per notes/replay.md: quarterly rounds on the clean window from 1 oct 2025 (15-min day-ahead on every layer), four rounds, q4 2025 to q3 2026. the imbalance replay is short because the data is: `ImbalancePrice` starts 4 mar 2025. every input is an estimated vintage, which flatters every method a little; said once here.

the ladder order and promotion rule are as committed in notes/replay.md before round 1.

## 2025q4 – persistence

config: replay/2025q4/plan.md. scorecard (replay/2025q4/scorecard.csv), 8,825 isps per horizon:

| h | mae | rmse | pinball | coverage | direction | brier | sign | pnl (10 mw, eur) |
|---|---|---|---|---|---|---|---|---|
| 15 | 128.7 | 174.4 | 42.2 | 0.794 | 0.501 | 0.998 | 0.555 | 141,940 |
| 30 | 134.8 | 181.8 | 44.2 | 0.797 | 0.482 | 1.036 | 0.535 | 82,785 |
| 60 | 138.3 | 186.1 | 45.3 | 0.796 | 0.478 | 1.045 | 0.529 | 46,635 |

review (draft, replay/2025q4/review.md): the evening reversals and the onshore shortfalls cost the most; the residual acf (0.62 at lag 1) says mean reversion is the next rung. change for round 2: add ar(1) as a challenger.

## 2026q1 – persistence, with ar(1) as challenger

config: replay/2026q1/plan.md (also fixes the rule for winning a round: lower mean pinball over the three horizons). scorecard, 8,636 isps per horizon:

| h | method | mae | rmse | pinball | coverage | direction | brier | sign | pnl (eur) |
|---|---|---|---|---|---|---|---|---|---|
| 15 | persistence | 150.5 | 204.6 | 49.5 | 0.789 | 0.515 | 0.970 | 0.568 | 185,755 |
| 15 | persistence_ar1 | 125.1 | 169.3 | 41.0 | 0.782 | 0.515 | 0.970 | 0.632 | 185,755 |
| 30 | persistence | 158.9 | 213.6 | 52.0 | 0.787 | 0.492 | 1.017 | 0.543 | 133,064 |
| 30 | persistence_ar1 | 128.3 | 172.9 | 42.0 | 0.782 | 0.492 | 1.017 | 0.615 | 133,064 |
| 60 | persistence | 166.3 | 222.7 | 54.5 | 0.789 | 0.480 | 1.041 | 0.528 | 147,490 |
| 60 | persistence_ar1 | 130.6 | 176.3 | 42.9 | 0.784 | 0.480 | 1.041 | 0.604 | 147,490 |

mean pinball over the horizons: persistence 52.0, ar(1) 41.9. **ar(1) wins and is the model for round 3.**

review (draft, replay/2026q1/review.md): ar(1) cuts the error by a fifth but can't see the wind: its worst isps are onshore running 1,000+ mw over the day-ahead forecast. change for round 3: seasonal naive as challenger, per the ladder.

## 2026q2 – ar(1), with seasonal naive as challenger

config: replay/2026q2/plan.md. scorecard, 8,718 isps per horizon (seasonal naive missing 13–14 without a lagged value):

| h | method | mae | rmse | pinball | coverage | direction | brier | sign | pnl (eur) |
|---|---|---|---|---|---|---|---|---|---|
| 15 | persistence_ar1 | 123.2 | 166.3 | 40.6 | 0.792 | 0.493 | 1.013 | 0.619 | 199,776 |
| 15 | seasonal_naive_day | 175.9 | 234.1 | 57.6 | 0.799 | 0.494 | 1.013 | 0.501 | 201,469 |
| 15 | seasonal_naive_week | 176.0 | 236.0 | 58.2 | 0.788 | 0.494 | 1.013 | 0.494 | 200,520 |
| 15 | persistence | 150.0 | 201.3 | 49.3 | 0.799 | 0.493 | 1.013 | 0.548 | 199,776 |
| 30 | persistence_ar1 | 125.2 | 169.4 | 41.3 | 0.793 | 0.482 | 1.036 | 0.609 | 165,370 |
| 30 | seasonal_naive_day | 175.9 | 234.1 | 57.6 | 0.799 | 0.482 | 1.036 | 0.501 | 166,872 |
| 30 | seasonal_naive_week | 176.0 | 236.0 | 58.3 | 0.787 | 0.482 | 1.037 | 0.494 | 165,291 |
| 30 | persistence | 154.6 | 207.0 | 50.8 | 0.799 | 0.482 | 1.036 | 0.534 | 165,370 |
| 60 | persistence_ar1 | 128.4 | 173.9 | 42.4 | 0.789 | 0.466 | 1.067 | 0.601 | 112,030 |
| 60 | seasonal_naive_day | 175.9 | 234.1 | 57.7 | 0.799 | 0.467 | 1.067 | 0.501 | 111,280 |
| 60 | seasonal_naive_week | 176.0 | 236.0 | 58.3 | 0.786 | 0.466 | 1.067 | 0.494 | 113,680 |
| 60 | persistence | 162.7 | 218.4 | 53.3 | 0.800 | 0.466 | 1.067 | 0.519 | 112,030 |

mean pinball over the horizons: ar(1) 41.5, seasonal naive (day) 57.6, (week) 58.3, persistence 51.1. **ar(1) stays the model.**

review (draft, replay/2026q2/review.md): the error moves to the solar hours (11:00–16:00); seasonal naive is worse than persistence. change for round 4: linear regression on lags and calendar as challenger; seasonal naive's last round.

## 2026q3 – ar(1), with the linear rung and seasonal naive as challengers

config: replay/2026q3/plan.md. scorecard, 8,831 isps per horizon:

| h | method | mae | rmse | pinball | coverage | direction | brier | sign | pnl (eur) |
|---|---|---|---|---|---|---|---|---|---|
| 15 | persistence_ar1 | 105.7 | 147.9 | 35.6 | 0.802 | 0.469 | 1.061 | 0.642 | 248,711 |
| 15 | linear_lags_calendar | 105.0 | 146.4 | 35.3 | 0.825 | 0.469 | 1.061 | 0.647 | 248,672 |
| 15 | seasonal_naive_day | 155.5 | 208.0 | 51.0 | 0.803 | 0.469 | 1.061 | 0.450 | 248,642 |
| 15 | seasonal_naive_week | 159.8 | 214.8 | 52.7 | 0.799 | 0.469 | 1.061 | 0.452 | 248,646 |
| 15 | persistence | 133.3 | 184.8 | 44.5 | 0.800 | 0.469 | 1.061 | 0.524 | 248,711 |
| 30 | persistence_ar1 | 106.7 | 149.4 | 36.1 | 0.797 | 0.456 | 1.087 | 0.641 | 211,219 |
| 30 | linear_lags_calendar | 106.0 | 148.0 | 35.7 | 0.827 | 0.456 | 1.087 | 0.643 | 211,194 |
| 30 | seasonal_naive_day | 155.5 | 208.0 | 51.0 | 0.803 | 0.456 | 1.087 | 0.450 | 211,150 |
| 30 | seasonal_naive_week | 159.8 | 214.8 | 52.7 | 0.799 | 0.456 | 1.087 | 0.452 | 211,219 |
| 30 | persistence | 137.8 | 190.1 | 45.9 | 0.800 | 0.456 | 1.087 | 0.513 | 211,219 |
| 60 | persistence_ar1 | 108.4 | 151.4 | 36.6 | 0.797 | 0.442 | 1.115 | 0.638 | 180,269 |
| 60 | linear_lags_calendar | 107.6 | 150.3 | 36.3 | 0.827 | 0.442 | 1.116 | 0.630 | 180,220 |
| 60 | seasonal_naive_day | 155.5 | 208.0 | 51.0 | 0.802 | 0.442 | 1.115 | 0.450 | 180,338 |
| 60 | seasonal_naive_week | 159.8 | 214.8 | 52.7 | 0.799 | 0.442 | 1.115 | 0.452 | 180,269 |
| 60 | persistence | 144.0 | 198.1 | 48.1 | 0.800 | 0.442 | 1.115 | 0.494 | 180,269 |

mean pinball over the horizons: linear 35.77, ar(1) 36.08, persistence 46.2, seasonal naive (day) 51.0, (week) 52.7. the linear rung is lower by under 1 % but was introduced this round, so it can't be promoted; **ar(1) is the replay's winner.** seasonal naive is dropped after its second round.

review (draft, replay/2026q3/review.md): a calmer quarter; my expectation that the hour dummies would win the solar hours was wrong, the linear rung's edge is spread thin and its band is too wide.

## where the replay leaves things

- four rounds reached rung 4 of the ten. arima, the exogenous regression, lightgbm, the quantile rungs, the council and ensembles never got a round: the clean window is four quarters long. the live record is where they go next, as challengers.
- per notes/replay.md the live model's starting config is the last round's winner: **ar(1)**. lightgbm-v1 (step 4) scored mean pinball 33.6 on 10 aug – 27 oct against ar(1)'s 36.1 on q3; different windows and lightgbm's settings were chosen on its own, so that's a hint, not a result.
- every rung so far is a volume method and calls direction like persistence. direction is the open problem.
- every round's worst isps are wind surprises the target's own history can't see: with onshore wind 300 mw or more above its day-ahead forecast at the freeze, the mae is 11 %, 28 %, 37 % and 56 % higher than inside ±100 mw, rising every round (persistence in round 1, ar(1) after).
- chart: replay/mae_by_round.png.
