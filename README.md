# nordcast

A public, tamper-evident forecast of the electricity imbalance in western Denmark (price area DK1), made every quarter-hour and scored against the grid operator's first published figure.

## What this is

Every 15 minutes, Energinet has to balance the Danish grid. When generation falls short of demand it activates up-regulation; when there is too much, down-regulation. nordcast forecasts, for each quarter-hour, which way the system will lean and by how many megawatts. It publishes three calls per quarter-hour, made 15, 30 and 60 minutes before it starts.

Each call is written to a file before its deadline, hashed, and timestamped once a day on the Bitcoin blockchain through OpenTimestamps. It is then scored against the first number Energinet publishes. Nothing is edited afterwards, so the track record below is the whole story: hits, misses and missed deadlines.

The 60-minute call is the last one that can still be traded on the intraday market. The 15- and 30-minute calls are for balancing decisions. The headline method today is the simplest possible one, persistence (the next quarter-hour looks like the last). A LightGBM model runs beside it as a challenger and may take over only under the rules in `notes/preregistration.md`, on 1 April 2027 at the earliest.

## How it works

1. **Archive.** A job pulls Energinet's live feeds every minute into daily Parquet files (the private `nordcast-archive` repository), so first prints are never lost.
2. **Store.** The feeds are loaded point-in-time into a local Postgres database. Every value keeps when it was for, when it was published and when it was pulled; a revision is a new row.
3. **Freeze.** Before each deadline the calls are written to `forecasts/frozen/`, hashed with SHA-256 and committed.
4. **Score.** Once Energinet's first print is in, each call is scored: direction hit or miss, and pinball loss on the volume range.
5. **Stamp and publish.** Each day's file is timestamped with OpenTimestamps and the scorecard below is rewritten by the job.
6. **Watch.** A heartbeat file is pushed hourly; a GitHub workflow raises an alert if it stops.

## A week of the target

![DK1 balancing energy and wind forecast error, 20 to 26 October 2026](notebooks/01_look.png)

Balancing needs swing between roughly plus and minus 500 MW within a day. The bottom panel shows the main driver the model can see: wind coming in above or below the day-ahead forecast.

## Scorecard

Live, from the scored record. The record started on 28 October 2026 and is far too short to judge; the jobs began running on a clock on 29 October, so the on-time share starts low and rises as the days accumulate.

<!-- scorecard -->
| horizon | method | calls | direction hit | pinball vs persistence (90 % CI) | coverage q10–q90 | on-time | live since |
|---|---|---|---|---|---|---|---|
| 15 min | headline | 6 | 0.0 % | +0.0 MW (+0.0 to +0.0) | 83.3 % | 5.9 % | 28 Oct 2026 |
| 15 min | lightgbm_v1 (challenger) | 3 | 66.7 % | +0.6 MW (+0.0 to +1.1) | 66.7 % | 3.0 % | 29 Oct 2026 |
| 30 min | headline | 5 | 20.0 % | +0.0 MW (+0.0 to +0.0) | 100.0 % | 4.9 % | 28 Oct 2026 |
| 30 min | lightgbm_v1 (challenger) | 2 | 0.0 % | -0.7 MW (-1.3 to +0.0) | 50.0 % | 2.0 % | 29 Oct 2026 |
| 60 min | headline | 3 | 0.0 % | +0.0 MW (+0.0 to +0.0) | 100.0 % | 2.9 % | 28 Oct 2026 |
<!-- /scorecard -->

How to read it:

- **calls** is the number of scored calls at that horizon.
- **direction hit** is the share of calls that named the right direction (up, down or none).
- **pinball vs persistence** is the improvement in pinball loss over plain persistence, in MW, with a 90 % bootstrap interval. Positive is better than persistence. For the headline it is zero by definition while persistence is the headline.
- **coverage q10–q90** is the share of first prints that fell inside the published range. The target is 80 %.
- **on-time** is the share of calls due since the record began that were frozen inside their window.
- **live since** is the first scored call.

## What the rehearsal said

Before going live, the methods were rehearsed on 2025 and 2026 data in quarterly rounds, each round adding one method. This is a replay on reconstructed data, not the live record.

![Mean absolute error by replay round](replay/mae_by_round.png)

The full log, with every round's configuration and review, is in `notes/replay-log.md`.

## How to run

The jobs are designed to run on one Mac, on a schedule, with a local Supabase database.

```bash
uv sync --all-groups                      # Python 3.12, dependencies
ops/start_stack.sh                        # Colima and Supabase, local Postgres on port 44332
uv run python jobs/pull_live.py           # load the latest feeds
uv run --group models python jobs/freeze.py   # freeze whatever is due
uv run python jobs/score.py               # score whatever has a first print
uv run pytest                             # tests, including the sign convention and the scorecard
```

`ops/install.sh` installs the three launchd agents (archive every minute, jobs every minute, stack at login). Charts are rebuilt with the two scripts in `notebooks/`; each has its command in its docstring.

## Layout

| Path | What it holds |
|---|---|
| `src/nordcast/` | The code: sources, schedule, freeze, score, scorecard, backup |
| `jobs/` | The scripts the scheduler calls, one per step |
| `ops/` | Install scripts and the launchd agents |
| `forecasts/frozen/` | The frozen calls, their hashes and the OpenTimestamps proofs |
| `supabase/migrations/` | The database schema |
| `notebooks/` | The two chart scripts and the notebooks they build |
| `replay/` | The rehearsal rounds: plan, review, diagnostics and scorecard for each |
| `notes/` | Design notes, the plan, the pre-registration, model cards and the incident log |
| `docs/` | A reader's index of the notes, and the analysis layers |
| `tests/` | pytest |
| `status/` | The heartbeat file the watchdog reads |

## Documents

Start with `docs/README.md`, which explains the notes and the project's phases in plain words. The binding documents are `notes/preregistration.md` (when the challenger may become the headline), `notes/nordcast-plan.md` (what gets built and in what order) and `notes/incidents.md` (every missed window, with its cause).

## Data and licence

Energinet, Energi Data Service: imbalance prices and direction, the real-time power system, 5-minute production and forecasts, and mFRR activations and requests. CC BY 4.0. eSett is the second price source. Nothing in this repository is paid data.

Prior art: `jacobazu/dk1-imbalance-forecasting` back-tests DK1 quarter-hour imbalance spreads, `siddiqov/dk-power-imbalance-trading` fits CatBoost to DK1 and DK2 imbalance prices, and `nordic-balancing` offers clients for eSett, Energinet and Fingrid prices. What nordcast adds is the record itself: frozen, hashed and timestamped calls scored against the first print, a direction class, a replay log and published intervals.

## Glossary

- **DK1**: the western Danish electricity price area (Jutland and Funen).
- **Quarter-hour, or ISP**: the imbalance settlement period, 15 minutes, the unit the grid is balanced over.
- **Up- and down-regulation**: turning generation up when the system is short, down when it is long.
- **mFRR and aFRR**: manual and automatic frequency restoration reserves, the balancing energy Energinet activates.
- **First print**: the first value Energinet publishes for a quarter-hour. Calls are scored against it, never against later revisions.
- **Point-in-time**: storing what was known when, so a forecast can only use data that existed at its deadline.
- **Freeze**: writing a call to disk before its deadline and hashing it, so it cannot be changed.
- **Persistence**: the baseline that says the next quarter-hour equals the last one.
- **AR(1)**: persistence with mean reversion, the rehearsal's best simple method.
- **Challenger**: a model that is frozen and scored beside the headline but is not the published call.
- **q10, q50, q90**: the 10th, 50th and 90th percentiles of the volume forecast; q10 to q90 is the published range.
- **Pinball loss**: the standard score for a quantile forecast; lower is better.
- **Coverage**: how often the true value fell inside the published range.
- **OpenTimestamps**: a free service that anchors a file hash in the Bitcoin blockchain, proving the file existed by that time.
- **Replay**: a rehearsal of the method on past data, round by round, before going live.
