# nordcast

Nordic imbalance nowcast: DK1 system imbalance direction and volume, 15/30/60 minutes ahead, frozen before delivery and scored against the first print.

![scorecard](docs/scorecard.png)

| horizon | calls | direction hit | pinball vs persistence (90% CI) | coverage q10–q90 | on-time | live since |
|---|---|---|---|---|---|---|
| 15 min | – | – | – | – | – | – |
| 30 min | – | – | – | – | – | – |
| 60 min | – | – | – | – | – | – |

Prior art: jacobazu/dk1-imbalance-forecasting, siddiqov/dk-power-imbalance-trading. What this adds: frozen, hashed, timestamped calls scored against the first print. Pre-registration: `notes/preregistration.md`. Data: Energinet (CC BY 4.0), DMI.
