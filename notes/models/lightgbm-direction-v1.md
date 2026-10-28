# lightgbm-direction-v1

```
model:          lightgbm-direction-v1
call:           dk1 dominating direction (ImbalancePrice.DominatingDirection) p_up/p_down/p_none, 15/30/60 min
status:         built 28 oct 2026, not frozen live yet (challenger from step 6; earliest promotion 1 apr 2027)
inputs:         as lightgbm-volume-v1 (same feature rows)
training:       as lightgbm-volume-v1: multiclass booster on the first 60 %, isotonic calibration
                (CalibratedClassifierCV on a FrozenEstimator) on 60-80 %, settings chosen by brier on the
                last 20 %; final: booster on 80 %, calibration on the last 20 %.
settings:       num_leaves 7 (15 at 60 min), n_estimators 150, learning_rate 0.05, min_child_samples 50
assumptions:    as lightgbm-volume-v1. the call is the most probable class.
known limits:   - barely better than nothing. accuracy 44.4 % at 15 min against 42.0 % for always "down";
                  brier 4.2 % below constant class shares at 15 min, 1.4 % at 60 min.
                - it never calls "none". none is 16 % of isps in the training window and 28 % in the last
                  20 %: the share rose after the 4 mar 2026 break, and a pooled window under-weights it.
                - its calls are 81-93 % "down", where the spread is small, so the hold-into-imbalance pnl
                  is below persistence's (table). a calibrated probability is not a trading signal.
                - the brier skill against persistence (41 %) is mostly persistence's one-hot probabilities;
                  the fair bar is constant shares.
pretraining:    n/a
validation:     not run.
version:        as lightgbm-volume-v1 (the direction model is in the same artefact)
changes:        28 oct 2026 first version.
                28 oct 2026 tried: fit on the post-4-mar-2026 window only (same validation slice). worse at
                every horizon (brier 0.682 vs 0.662 at 15 min; 0.693 at 60, no better than constant
                shares) and it still calls none on 0-0.3 % of isps. kept the pooled window.
```

## result on the last 20 % (10 aug – 27 oct 2026, 7,522 isps), notebooks/03_model.ipynb

optimistic, as for volume. pnl: 10 mw open in the called direction, settled at the first-print imbalance price against day-ahead, eur summed over the 11 weeks, no costs.

| h | accuracy lightgbm / persistence / always down | brier lightgbm / persistence / constant shares | pnl lightgbm / persistence (eur) |
|---|---|---|---|
| 15 | 0.444 / 0.435 / 0.420 | 0.662 / 1.130 / 0.691 | 125,757 / 248,786 |
| 30 | 0.427 / 0.422 / 0.420 | 0.671 / 1.155 / 0.691 | 25,187 / 202,746 |
| 60 | 0.424 / 0.406 / 0.420 | 0.681 / 1.188 / 0.691 | −13,305 / 142,300 |

a perfect direction call would have made 1,081,220 eur on the same window, so the money is in the up isps (mean spread +97 eur/mwh) and persistence catches more of them by holding the last direction through runs. the post-4-mar-2026 fit was tried and was worse (changes, above). none is 28 % of the last 20 % against 42 % down, so it is rarely the most probable class even when its probability is right: the argmax rarely picks it by construction. next to try: a threshold on p_none, or recency weights, instead of cutting the window.
