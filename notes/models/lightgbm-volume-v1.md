# lightgbm-volume-v1

```
model:          lightgbm-volume-v1
call:           dk1 imbalance volume (ImbalancePrice.SatisfiedDemand, mw, + up) q10/q50/q90, 15/30/60 min
status:         challenger, frozen live beside persistence as lightgbm_v1 from step 6 (29 oct 2026 code;
                the record starts when ops/install.sh runs). earliest promotion 1 apr 2027, per
                notes/preregistration.md
inputs:         energinet.dk1.{satisfied_demand, dominating_direction, imbalance_price_eur, afrr_up_mw,
                afrr_down_mw, mfrr_up_mw, mfrr_down_mw, da_price_eur, wind_onshore_mw, wind_offshore_mw,
                solar_mw, wind_onshore_fc_da_mw, wind_offshore_fc_da_mw, solar_fc_da_mw,
                wind_onshore_fc_1h_mw, wind_offshore_fc_1h_mw}, all read through history (value_asof
                semantics), asof = isp start - h - 5 min
training:       1 oct 2025 - 27 oct 2026, 37,606 isps per horizon, estimated vintages. boosters on the first
                60 %, conformal band (mapie ConformalizedQuantileRegressor, 80 %) on 60-80 %, settings chosen
                by mean pinball on the last 20 %; final model: boosters on 80 %, band on the last 20 %.
                not refit weekly yet.
settings:       num_leaves 7, n_estimators 150, learning_rate 0.05, min_child_samples 50 (all horizons)
assumptions:    - estimated publish times (notes/sources.md) err late, so training sees the target one isp
                  staler than live does (4 isps back at 15 min, live 3). live serving applies the same
                  lags (challenger.nominal) and reads at min(now, isp start - h - 5 min); tested equal to a
                  training row in tests/test_challenger.py.
                - missing inputs are nan and lightgbm routes them down a learned branch. at 60 min the
                  1-hour wind forecasts are always missing (published 51 min before the isp).
                - offshore wind is used only as its own error against its own forecast: the 5-min feed and
                  the forecasts define offshore differently (~900 mw level gap, 27 oct 2026).
                - 4 mar 2026 break (SatisfiedDemand: demand -> activated) enters as regime_activated, 0/1.
known limits:   - mfrr_request (energinet's own request, from 7.5 min before the mtu) has no history before
                  28 oct 2026, so it isn't an input. it should be the strongest one for 15 min.
                - the chosen settings sit at the small corner of the grid (7 leaves, 150 trees), twice: the
                  grid was moved down once and the corner moved with it. the model is near the edge of
                  what this window supports; a smaller grid or more regularisation is the next thing to try.
                - nothing seen of mari (q1 2027): retrain at that boundary.
                - one regime-pooled model; the 4 mar 2026 split is a feature, not separate fits.
pretraining:    n/a
validation:     not run. checklist in controls.md §3, in a fresh session.
version:        code c775fdb + uncommitted step-4 work (features.py, model.py, jobs/train.py);
                artefacts data/models/lightgbm-v1-h{15,30,60}.pkl sha256
                h15 db327da0b1b40b02…, h30 c9ecf0d189d719af…, h60 a067374958c4c99a… (full in manifest.json)
changes:        28 oct 2026 first version.
                29 oct 2026 frozen live as a challenger (no refit; artefacts unchanged).
                28 oct 2026 tried: post-4-mar-2026 window only. worse at every horizon (pinball 33.4 vs
                33.2 at 15 min, 35.0 vs 34.3 at 60). kept the pooled window.
```

## result on the last 20 % (10 aug – 27 oct 2026, 7,522 isps), notebooks/03_model.ipynb

optimistic: settings were chosen on this same window, and the inputs are estimated vintages.

| h | mae lightgbm / persistence | pinball lightgbm / persistence | skill (pinball) | coverage q10–q90 |
|---|---|---|---|---|
| 15 | 98.8 / 126.8 | 33.2 / 42.4 | 21.8 % | 0.846 |
| 30 | 98.9 / 130.8 | 33.4 / 43.8 | 23.7 % | 0.845 |
| 60 | 101.6 / 135.5 | 34.3 / 45.5 | 24.5 % | 0.853 |

the band is a little wide: 85 % inside, against 80 % stated (the controls range is 70–90 %). the raw quantiles cover the same as the conformal band, so mapie barely moves them. the volume model leans on the latest target value (35 % of gain at 15 min), then the onshore and offshore day-ahead errors, the solar forecast and the hour.
