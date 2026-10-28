# 2026q3 – plan

written 28 oct 2026, before the round ran. round 4: 1 jul – 30 sep 2026 (copenhagen), the last round of the clean window.

- method: persistence_ar1
- method: linear_lags_calendar
- method: seasonal_naive_day
- method: seasonal_naive_week
- method: persistence

**the model: persistence_ar1** (won round 2, held round 3). **challengers:** rung 4, `linear_lags_calendar`, new this round; seasonal naive (day, week) in its second and last round, dropped after it unless it wins. persistence stays as the floor. winning: lower mean pinball over the three horizons.

config:
- persistence_ar1, seasonal naive: unchanged.
- linear_lags_calendar: ordinary least squares on sd_lag1–4, sd_mean4 and regime_activated, with dummies for copenhagen hour, quarter of the hour and weekday (one level each dropped against the intercept). refit every copenhagen monday on every training row whose isp was at least a day old by then, from 1 oct 2025. band: 10th / 90th percentile of the fit's own residuals, added to the point. direction: persistence's (a volume method). rows with a lag missing are counted as missing, never filled.

**review change from round 3:** the new rung, per the ladder. round 3 pointed at the solar hours; the hour dummies are the first thing on the ladder that can see time of day at all.

what I expect: the linear rung beats ar(1) on the solar hours (11:00–16:00) and loses or ties overnight; overall close.
