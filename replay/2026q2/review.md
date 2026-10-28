# 2026q2 – review

draft from scorecard.csv and diagnostics.md only; edit before round 4.

**what was wrong.** ar(1) held: mae 123 mw at 15 min (128 at 60), mean pinball 41.5 against persistence's 51.1. seasonal naive lost as expected: mae 176 mw at every horizon, pinball 57.6 (yesterday) and 58.2 (last week), worse than persistence. coverage 79 % for ar(1).

**where.** the error now follows the sun: ar(1)'s mae is 170 mw at 11:00 and 166–168 at 15:00–16:00, against 83–98 between 22:00 and 05:00. in q1 the hours were flatter (108–147). onshore wind still matters at both tails: 169 mw with the error below −300, 152 above +300, 111 inside ±100. the biggest misses are a run on 20 jun 03:30–04:00, the system turning from +500 to −1,382 mw before dawn with no wind signal, and 27–28 jun around midday.

**why.** solar ramps, which ar(1) can't see: the day-ahead solar forecast and its error both correlate −0.09 with the target in the training rows.

**next round.** ar(1) stays the model. rung 4, a linear regression on lags and calendar, as the new challenger; seasonal naive gets its second and last round.

**not changing.** the band.
