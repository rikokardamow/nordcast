# 2026q1 – review

draft from scorecard.csv and diagnostics.md only; edit before round 3.

**what was wrong.** persistence got worse than in q4: mae 151 mw at 15 min (166 at 60). ar(1) cut that to 125 (131 at 60), and mean pinball from 49.5 to 41.0 at 15 min, 17–21 % lower at every horizon. direction is persistence's in both: 52 % at 15 min.

**where.** ar(1) is worst when onshore wind runs above its day-ahead forecast: mae 140 mw with the error above +300 mw, against 109 inside ±100. that was 41 % of the round's isps, so the day-ahead onshore forecast ran low most of the quarter. the misses that matter most: 24 mar 21:15–21:30 and 27 mar 20:45, onshore 1,050–1,140 mw above forecast, the system at −1,000 to −1,180 mw, ar(1) near −50. the 4 mar break barely shows: 124.5 mw before, 126.5 after.

**why.** ar(1) only knows the target. the residual acf is still 0.70 at lag 1: the structure it leaves is the wind error, which it can't see.

**next round.** ar(1) wins and is the model. rung 3, seasonal naive, as challenger. one change.

**not changing.** the band.
