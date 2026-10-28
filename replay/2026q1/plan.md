# 2026q1 – plan

written 28 oct 2026, before the round ran. round 2: 1 jan – 31 mar 2026 (copenhagen). the 4 mar 2026 break (SatisfiedDemand: demand -> activated) falls inside this round; the diagnostics split on it.

- method: persistence
- method: persistence_ar1

**the model: persistence** (round 1's only method). **challenger: persistence_ar1**, rung 2, introduced this round per the round 1 review (residual acf 0.62 at lag 1). it can't be promoted this round.

config, as frozen live (src/nordcast/baselines.py):
- persistence: unchanged from round 1.
- persistence_ar1: point = mu + phi^k (last − mu), k the isps between the last known and the target; phi (clipped to 0–1) and mu fitted on the 7 days of first prints before each freeze, so it refits continuously, not weekly. band: q10/q90 of its own k-step residuals over the same 7 days. direction: persistence's (ar(1) is a volume method), so direction scores equal persistence's.

**winning a round** (fixed here, for every round from now): the lower mean pinball averaged over the three horizons. a challenger that wins becomes the model for the next round; one that loses stays a challenger for one more round, then is dropped and logged.

**review change from round 1:** none to persistence; the band stays as it is.
