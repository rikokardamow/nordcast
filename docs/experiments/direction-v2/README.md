# Experiment: can the direction call beat hour-of-day climatology by more? (29 Oct 2026)

**In plain English.** Can two cheap ideas widen the model's narrow lead on the up-or-down forecast? No, though blending it with the usual hour-of-day pattern never hurt, so it is a useful safeguard.

**Question.** [direction-bar](../direction-bar/README.md) found lightgbm_v1's direction ahead of hour-of-day climatology by only 0.01–0.03 Brier at 15–30 min, and behind it at 60 min in 2026q3. Do two cheap ideas widen that?

**Answer: no, but one is a useful guard.** Feeding climatology to LightGBM as features (`stack`) doesn't help and is slightly worse in 2026q2–q3. Blending v1 with climatology (`blend`, weight chosen on data before each round) never hurt: it picked w = 1 (v1 itself) in 2026q1–q2 and leaned toward climatology in 2026q3, where it beat v1 and turned v1's 60-minute loss to climatology into a draw. Research only; lightgbm_v1 and the pre-registration are untouched.

**Method** ([run.py](run.py), results in [results.csv](results.csv)). Out of sample on the replay's 2026 rounds, refit before each with v1's procedure and settings. Climatology: each direction's share at the target's Copenhagen hour over the 28 days before the target's day, add-one smoothed (as in direction-bar). `blend` = w · v1 + (1 − w) · climatology, w from 0 to 1 in steps of 0.1, chosen by Brier on the calibration slice (the last 25 % before the round; v1's isotonic step was fitted there too, which favours v1 and so pushes w up). `stack` = v1 refit with the three climatology probabilities as features. Gain = mean daily fall in Brier, day-block bootstrap 90 % interval.

| h | round | w | Brier clim. | v1 vs clim. | blend vs clim. | stack vs clim. | blend vs v1 |
|---|---|---|---|---|---|---|---|
| 15 | 2026q1 | 1.0 | 0.590 | +0.028 (+0.020 to +0.036) | = v1 | +0.029 (+0.021 to +0.037) | 0 |
| 15 | 2026q2 | 1.0 | 0.578 | +0.022 (+0.013 to +0.030) | = v1 | +0.019 (+0.011 to +0.028) | 0 |
| 15 | 2026q3 | 0.9 | 0.621 | +0.016 (+0.009 to +0.023) | +0.019 (+0.012 to +0.025) | +0.013 (+0.004 to +0.021) | **+0.003 (+0.002 to +0.003)** |
| 30 | 2026q1 | 1.0 | 0.590 | +0.015 (+0.007 to +0.023) | = v1 | +0.016 (+0.008 to +0.024) | 0 |
| 30 | 2026q2 | 1.0 | 0.578 | +0.015 (+0.007 to +0.024) | = v1 | +0.011 (+0.002 to +0.020) | 0 |
| 30 | 2026q3 | 0.9 | 0.621 | +0.009 (+0.003 to +0.016) | +0.012 (+0.006 to +0.018) | +0.007 (−0.000 to +0.014) | **+0.003 (+0.002 to +0.003)** |
| 60 | 2026q1 | 1.0 | 0.590 | +0.006 (−0.003 to +0.015) | = v1 | +0.007 (−0.001 to +0.016) | 0 |
| 60 | 2026q2 | 1.0 | 0.579 | +0.003 (−0.006 to +0.010) | = v1 | −0.002 (−0.011 to +0.008) | 0 |
| 60 | 2026q3 | 0.8 | 0.621 | **−0.012 (−0.019 to −0.004)** | −0.003 (−0.008 to +0.003) | −0.012 (−0.019 to −0.004) | **+0.009 (+0.007 to +0.011)** |

**Reading.**
- Climatology carries little that v1 doesn't already have (the hour is a v1 feature), so stacking it adds nothing.
- The blend is a shrinkage toward the base rate. It is free when v1 is good (w = 1) and limits the damage when v1 drifts, as in 2026q3, when "none" rose to 21 % of ISPs. For a later direction model, shrinking toward climatology with a weight refit on recent data is the cheap guard to build in.
- Neither idea moves the 15–30 minute edge beyond about 0.03 Brier. Direction stays the open problem; the inputs that might change that (mfrrRequest, first archived 28 Oct 2026) don't have the history yet.
