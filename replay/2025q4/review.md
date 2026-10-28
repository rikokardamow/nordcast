# 2025q4 – review

draft by claude code from scorecard.csv and diagnostics.md only; edit before round 2.

**what was wrong.** persistence missed by 129 mw on average at 15 min (138 at 60), rmse 174–186. the band held: 79–80 % of first prints inside q10–q90. direction was right 50 % at 15 min, 48 % at 60, against 67 % down in the year before.

**where.** the evening peak: mae 161 mw at 17:00 against 106 at 22:00 and 109–115 at 02:00–05:00. six of the ten biggest misses are between 17:00 and 21:15; three of those six are sign reversals, the rest a quiet last isp before a large one. mae rises to 168 mw when onshore wind was 300 mw or more below its day-ahead forecast, against 119 mw when the error was inside ±100 mw. 22 nov 20:15 (−1,758 mw, missed by 1,578) fell inside a data gap: energinet's 5-min production is missing 21–22 nov and the day-ahead wind forecast 22–24 nov.

**why.** the residual acf is 0.62 at lag 1 and −0.43 at lag 4: errors persist, then flip as the system reverts.

**next round.** rung 2, ar(1) mean reversion, as a challenger. one change.

**not changing.** the band: coverage is on target.
