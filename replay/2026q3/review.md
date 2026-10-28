# 2026q3 – review

draft from scorecard.csv and diagnostics.md only; edit before the pre-registration.

**what was wrong.** the quarter was calmer: ar(1) mae 106 mw at 15 min (108 at 60), mean pinball 36.1, persistence 46.2. the linear rung came in at 35.8, under 1 % better, and its band is too wide (82.5–82.7 % inside q10–q90 against 80 % stated). seasonal naive lost again (51.0 and 52.7) and is dropped.

**where.** my plan expected the linear rung to win the solar hours. it didn't: hour by hour the two are within 3 mw. its small edge is spread across the day. both are worst with onshore wind above forecast by 300 mw or more (136–137 mw, 2,142 isps). the biggest miss: 4 sep 19:15, −1,120 mw with onshore 514 and offshore 814 mw above forecast.

**why.** the hour dummies add little that the lags don't already carry; the wind error is still what's left.

**next.** rounds end here. the linear rung can't be promoted on the round it entered, so ar(1) is the replay's winner. the two are within noise: a second round would trigger rung 10's ensemble rule.

**not changing.** direction: every rung so far uses persistence's.
