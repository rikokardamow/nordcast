# 2025q4 – plan

written 28 oct 2026, before the round ran.

round 1 of the replay: 1 oct – 31 dec 2025 (copenhagen), the first quarter of the clean window (15-min day-ahead on every layer). per the ladder in notes/replay.md, round 1 is persistence only: the point is to see how hard it is to beat.

- method: persistence

config, as frozen live (src/nordcast/baselines.py):
- volume: the latest isp known at the freeze. the band is q10/q90 of that isp plus the 10th/90th percentile of same-gap changes over the 7 days before the freeze.
- direction: the latest known isp's direction, with all its probability.
- horizons 15, 30, 60 min, as of isp start − h − 5 min; estimated vintages (notes/sources.md).

next round introduces rung 2 (persistence + ar(1) mean reversion) as a challenger, scored against persistence; it can't be promoted on the round it's introduced.

the analysis runs on the year before 1 oct 2025, which spans the 4 mar 2025 eam go-live, the 19 mar 2025 price change and the 2 jun 2025 25 mw threshold: three designs, so read its profiles as indicative.
