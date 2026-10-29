# Experiment: is persistence a real bar for the direction call? (29 Oct 2026)

**Question.** `notes/preregistration.md` tests lightgbm_v1's direction by its Brier score against persistence. Persistence's direction "probabilities" are one-hot (1 on its call), so does that test say anything?

**Answer: no. Against persistence the Brier condition is a formality; against direction climatology it's a real test, which v1 passes narrowly at 15 and 30 min and not at 60 min.** Research only; nothing in the record or the pre-registration changed.

**Method** ([run.py](run.py), results in [results.csv](results.csv)). Out of sample on the replay's 2026 rounds. `v1`: LightGBM v1's calibrated probabilities, refit before each round as in [v2-layer-features](../v2-layer-features/README.md). `persistence`: one-hot on the last known direction. `climatology`: each direction's share at the target's Copenhagen hour over the 28 days before the target's day, add-one smoothed (a day staler than the live `direction_climatology` baseline, so conservative for climatology). Gain = mean daily fall in Brier, day-block bootstrap 90 % interval.

| h | round | Brier persistence | Brier climatology | Brier v1 | v1 vs persistence | v1 vs climatology | accuracy v1 / pers. / clim. |
|---|---|---|---|---|---|---|---|
| 15 | 2026q1 | 0.970 | 0.589 | 0.561 | +0.41 (+0.38 to +0.44) | **+0.028 (+0.019 to +0.036)** | 54 / 52 / 52 % |
| 15 | 2026q2 | 1.013 | 0.578 | 0.557 | +0.46 (+0.43 to +0.48) | **+0.022 (+0.013 to +0.030)** | 56 / 49 / 53 % |
| 15 | 2026q3 | 1.061 | 0.621 | 0.604 | +0.46 (+0.44 to +0.48) | **+0.016 (+0.009 to +0.023)** | 51 / 47 / 49 % |
| 30 | 2026q1 | 1.017 | 0.589 | 0.574 | +0.44 (+0.41 to +0.47) | **+0.015 (+0.007 to +0.023)** | 53 / 49 / 52 % |
| 30 | 2026q2 | 1.036 | 0.578 | 0.563 | +0.47 (+0.44 to +0.50) | **+0.015 (+0.007 to +0.024)** | 55 / 48 / 53 % |
| 30 | 2026q3 | 1.087 | 0.621 | 0.611 | +0.48 (+0.45 to +0.50) | **+0.009 (+0.003 to +0.016)** | 50 / 46 / 49 % |
| 60 | 2026q1 | 1.041 | 0.589 | 0.583 | +0.46 (+0.43 to +0.49) | +0.006 (−0.003 to +0.015) | 53 / 48 / 52 % |
| 60 | 2026q2 | 1.067 | 0.579 | 0.576 | +0.49 (+0.46 to +0.52) | +0.002 (−0.006 to +0.010) | 53 / 47 / 53 % |
| 60 | 2026q3 | 1.115 | 0.621 | 0.632 | +0.48 (+0.46 to +0.51) | −0.012 (−0.019 to −0.004) | 49 / 44 / 49 % |

**Reading.**
- Persistence's Brier is about 1.0 because a one-hot call that's wrong scores 2. Any calibrated model clears it by ~0.45; the pre-registered direction condition will pass whether or not v1 knows anything about direction.
- Climatology, which only knows the hour of day, is the honest bar: v1 beats it by 0.01–0.03 at 15–30 min, shrinking each quarter, and not at 60 min (worse in 2026q3).
- "None" grew from 12 % of ISPs in 2026q1 to 21 % in 2026q3; every method's accuracy fell with it.

**Proposed amendment** (the owner's decision; the pre-registration says changes go in as dated amendments, and the challenger's window hasn't opened):

> *Amendment 1, <date>.* For direction, the Brier comparison is made against `direction_climatology` as well as persistence, on the same window, bootstrap and 90 % interval. The challenger passes on direction only if its interval against climatology is above zero. Reason: persistence's one-hot probabilities score ~1.0 Brier, so beating it is not evidence of skill (docs/experiments/direction-bar, 29 Oct 2026).
