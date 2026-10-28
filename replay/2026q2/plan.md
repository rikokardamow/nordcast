# 2026q2 – plan

written 28 oct 2026, before the round ran. round 3: 1 apr – 30 jun 2026 (copenhagen), wholly after the 4 mar 2026 break.

- method: persistence_ar1
- method: seasonal_naive_day
- method: seasonal_naive_week
- method: persistence

**the model: persistence_ar1**, promoted on round 2 (mean pinball 41.9 against persistence's 52.0). **challenger: seasonal naive**, rung 3, in its two forms from notes/replay.md: the same isp yesterday and the same isp a week ago. persistence stays in the table as the floor. a challenger can't be promoted this round; winning is the lower mean pinball over the three horizons (round 2's plan).

config:
- persistence_ar1: unchanged from round 2.
- seasonal_naive_day / _week: the same isp 1 / 7 days before, as first known at the freeze (isp start − h − 5 min). band: the 10th / 90th percentile of 1-day / 7-day changes over the 7 days before the freeze. direction: persistence's (volume methods). an isp without the lagged value is counted as missing and left out of the score, never filled.

**review change from round 2:** none to the model: rung 3 enters per the ladder. the round 2 review pointed at the wind error, which is rung 6; the ladder doesn't skip.

what I expect, written down so I can't move it later: seasonal naive loses badly. the round 2 analysis had the acf at a day at 0.12.
