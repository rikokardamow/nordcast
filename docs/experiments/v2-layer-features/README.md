# Experiment: layers #31–#33 as LightGBM inputs (29 Oct 2026)

**In plain English.** Could the machine-learning model get more from the residual-load, border-flow and price-spread data than a simple model did? No. This was research only and changed nothing in the live forecast.

**Question.** The three DK1 layers (residual load, interconnector flows, day-ahead spreads) each failed a linear test. Does LightGBM, which can use them non-linearly, find what the linear model didn't?

**Answer: no.** Research only; lightgbm_v1 (the live challenger) and `notes/preregistration.md` are untouched.

**Method** ([run.py](run.py), results in [results.csv](results.csv)). For each of the replay's 2026 rounds and each horizon, two LightGBM sets fitted with v1's own procedure (`model._fit`: quantile boosters, MAPIE 80 % band, isotonic direction) and v1's chosen settings, on every row before the round (boosters on the first 75 %, calibration on the last 25 %), scored on the round. `v1` = v1's features; `v1+lay` = those plus the 12 layer features (residual load 3, interconnectors 4, spreads 5). Gain = mean daily fall in loss, day-block bootstrap 90 % interval. v1's settings were chosen on v1's features, which favours v1 a little.

| h | round | pinball v1 | gain in pinball (MW) | Brier v1 | gain in Brier |
|---|---|---|---|---|---|
| 15 | 2026q1 | 40.0 | −0.09 (−0.33 to +0.13) | 0.561 | −0.001 (−0.005 to +0.003) |
| 15 | 2026q2 | 38.8 | **+0.43 (+0.20 to +0.66)** | 0.557 | +0.004 (+0.000 to +0.007) |
| 15 | 2026q3 | 34.4 | +0.10 (−0.08 to +0.29) | 0.605 | **+0.004 (+0.001 to +0.007)** |
| 30 | 2026q1 | 41.1 | −0.13 (−0.40 to +0.13) | 0.574 | −0.001 (−0.005 to +0.002) |
| 30 | 2026q2 | 39.5 | +0.17 (−0.06 to +0.39) | 0.563 | +0.001 (−0.001 to +0.004) |
| 30 | 2026q3 | 35.2 | +0.09 (−0.10 to +0.29) | 0.611 | −0.002 (−0.006 to +0.001) |
| 60 | 2026q1 | 42.2 | +0.11 (−0.13 to +0.34) | 0.583 | +0.001 (−0.003 to +0.005) |
| 60 | 2026q2 | 40.4 | +0.09 (−0.18 to +0.37) | 0.576 | +0.000 (−0.003 to +0.003) |
| 60 | 2026q3 | 36.0 | −0.06 (−0.20 to +0.07) | 0.632 | **+0.008 (+0.004 to +0.012)** |

**Reading.** Every change is about 1 % or less of the loss, the sign varies by round and horizon, and 3 of 18 intervals clear zero, about what chance gives across 18 tests. No v2 on this evidence. If one is tried later, a year more of data would be the reason, not these numbers.

**Side finding, for v1's model card.** Trained only on the months before 2026q1 (Oct–Dec 2025), v1's 80 % band covered 69–73 % in that quarter; with more history it covered 81–84 % in 2026q2–q3. The band is under-wide when the training window is short.
