# nordcast

nordcast forecasts the short-term power imbalance in western Denmark, publishes a forecast every quarter-hour, and keeps score in public.

Electricity supply and demand must match at every moment, but plans never hold exactly. Energinet, which runs the Danish grid, makes up the difference every 15 minutes. If generation falls short it buys extra power (up-regulation), and if there is too much it pays to reduce it (down-regulation). nordcast predicts which way that will go and by how many megawatts (MW), 15, 30 and 60 minutes ahead.

**The point is the record, more than the model.** Each forecast is saved before its deadline, with a timestamped fingerprint that proves when it was made. Once Energinet publishes the result, the forecast is scored against that first number. Nothing is revised afterwards, so misses and missed deadlines stay in the table.

**The official forecast is deliberately simple for now.** It is *persistence*: the next quarter-hour will look like the last one. A machine-learning model (LightGBM) runs beside it on the same terms. The model can only replace persistence if it passes a test written down in advance in `notes/preregistration.md`, and not before 1 April 2027.

![DK1 system imbalance and wind forecast error, 20 to 26 October 2026](notebooks/01_look.png)

The top panel shows what is being forecast: the balancing energy Energinet used in each quarter-hour. The bottom panel shows the main thing a model can see coming: wind power arriving above or below the forecast made the day before.

## Scorecard

Updated automatically each day. The record only started on 28 October 2026, so for now these numbers say very little. The on-time share starts low and should rise as the days add up.

<!-- scorecard -->
| looking ahead | forecast | scored | right direction | gain on persistence | inside its range (target 80 %) | on time |
|---|---|---|---|---|---|---|
| 15 min | official forecast | 23 | 26.1 % | +0.0 MW | 95.7 % | 9.5 % |
| 15 min | lightgbm_v1 (challenger) | 20 | 45.0 % | +6.0 MW | 90.0 % | 8.3 % |
| 30 min | official forecast | 23 | 39.1 % | +0.0 MW | 100.0 % | 9.5 % |
| 30 min | lightgbm_v1 (challenger) | 20 | 35.0 % | +5.9 MW | 90.0 % | 8.2 % |
| 60 min | official forecast | 23 | 47.8 % | +0.0 MW | 100.0 % | 9.4 % |
| 60 min | lightgbm_v1 (challenger) | 20 | 30.0 % | +6.0 MW | 90.0 % | 8.2 % |

<details><summary>Full table, with the pre-registered statistics</summary>

| horizon | method | calls | direction hit | pinball vs persistence (90 % CI) | Brier vs persistence | Brier vs climatology | coverage q10–q90 | on-time | live since |
|---|---|---|---|---|---|---|---|---|---|
| 15 min | headline | 23 | 26.1 % | +0.0 MW (+0.0 to +0.0) | +0.000 (+0.000 to +0.000) | -0.646 (-1.236 to +0.072) | 95.7 % | 9.5 % | 28 Oct 2026 |
| 15 min | lightgbm_v1 (challenger) | 20 | 45.0 % | +6.0 MW (+3.5 to +8.4) | +0.301 (-0.088 to +0.772) | -0.345 (-0.839 to +0.149) | 90.0 % | 8.3 % | 29 Oct 2026 |
| 30 min | headline | 23 | 39.1 % | +0.0 MW (+0.0 to +0.0) | +0.000 (+0.000 to +0.000) | -0.698 (-1.068 to -0.351) | 100.0 % | 9.5 % | 28 Oct 2026 |
| 30 min | lightgbm_v1 (challenger) | 20 | 35.0 % | +5.9 MW (+3.4 to +8.4) | +0.345 (+0.135 to +0.528) | -0.353 (-0.764 to +0.058) | 90.0 % | 8.2 % | 29 Oct 2026 |
| 60 min | headline | 23 | 47.8 % | +0.0 MW (+0.0 to +0.0) | +0.000 (+0.000 to +0.000) | -0.717 (-1.136 to -0.345) | 100.0 % | 9.4 % | 28 Oct 2026 |
| 60 min | lightgbm_v1 (challenger) | 20 | 30.0 % | +6.0 MW (+2.3 to +9.7) | +0.237 (+0.045 to +0.533) | -0.480 (-0.902 to -0.059) | 90.0 % | 8.2 % | 29 Oct 2026 |

</details>
<!-- /scorecard -->

How to read it:

- **Scored:** how many forecasts have a result so far.
- **Right direction:** how often the forecast named the right direction (up, down or neither).
- **Gain on persistence:** how much better the size forecast was than persistence, in MW. Above zero is better. The official forecast shows zero because it currently is persistence.
- **Inside its range:** how often the result fell inside the forecast's published range. The target is 80%.
- **On time:** the share of forecasts due since the start that were saved before their deadline.

## Before going live

The methods were first rehearsed on 2025 and 2026 data, one quarter at a time, adding one method each round. Lower error is better. This used reconstructed data, so it isn't part of the record, but it explains why persistence plus mean reversion (assuming the imbalance drifts back towards normal) is next in line.

![Replay: mean absolute error of the 15-minute call, by round](replay/mae_by_round.png)

The full log of each round, with the configuration and the review, is in `notes/replay-log.md`.

## Running it

The jobs run on one Mac against a local Supabase database.

```bash
uv sync --all-groups
ops/start_stack.sh                          # Colima and Supabase; Postgres on port 44332
uv run python jobs/pull_live.py             # load the latest feeds
uv run --group models python jobs/freeze.py # freeze whatever is due
uv run python jobs/score.py                 # score whatever has an outcome
uv run pytest
```

`ops/install.sh` sets up four launchd agents: an archive job every minute, the forecasting jobs every minute, the database stack at login, and a watchdog that reloads any of them launchd has lost. The two charts above are rebuilt by the scripts in `notebooks/`; the command is in each docstring.

## Where things are

- `src/nordcast/` is the code: data sources, the schedule, freezing, scoring, the scorecard, backups.
- `jobs/` has one script per scheduled step and `ops/` the launchd agents that call them.
- `forecasts/frozen/` holds every frozen forecast with its hash and timestamp proof.
- `notes/` is the working record: the plan, the pre-registration, the data register, model cards and the incident log. `docs/README.md` explains how they fit together.
- `replay/` has the rehearsal rounds, `tests/` the tests, `supabase/migrations/` the schema.

Raw feeds are archived every minute to a private repository, `nordcast-archive`, so that first prints are never lost, and the database is backed up hourly to `nordcast-backups`.

## Data

Energinet's Energi Data Service, CC BY 4.0: imbalance prices and direction, the real-time power system feed, five-minute production and forecasts, and mFRR activations and requests. eSett is used as a second source for prices.

Related work: `jacobazu/dk1-imbalance-forecasting` back-tests DK1 imbalance spreads, `siddiqov/dk-power-imbalance-trading` fits CatBoost to DK1 and DK2 imbalance prices, and `nordic-balancing` provides clients for eSett, Energinet and Fingrid prices. What this project adds is the record itself: frozen, hashed, timestamped forecasts scored against the first print, a separate direction call, and a replay log.
