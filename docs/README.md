# Reading guide

nordcast's working notes are written for the person building it, so they use short names and internal numbering. This page says what each one is for and what the numbering means. The README is the plain summary; this is the map.

## The idea in one paragraph

A forecast is only worth trusting if you can prove when it was made. nordcast makes a call for every quarter-hour of the DK1 grid, writes it to disk before the deadline, hashes it, timestamps the day's file on the Bitcoin blockchain, and scores it against Energinet's first published value. That scored history is "the record". Everything else in the repository exists to make the record run on time, or to decide what method should be making the call.

## Phases and gates

The plan (`notes/nordcast-plan.md`) builds in phases. A phase opens only when the gate before it is passed.

| Phase | What it builds | Gate to the next |
|---|---|---|
| 0, archive | A job that saves Energinet's live feeds every minute, so first prints are never lost | Sign convention checked and tested |
| 1, the record | Store, baselines, persistence live, LightGBM as challenger, scoring, daily timestamp, heartbeat | G1: 30 days in a row with at least 99 % of calls frozen on time and no open incident |
| 2, value | What the call is worth as a 10 MW position; zero-shot foundation models as challengers | G2: 90 days live, the challenger promoted or explicitly not |
| 3, book and risk | Risk limits, value-at-risk, a simulated wind-park book | |
| 4, site | A website and an order-book simulator, no earlier than mid-2027 | |

"Step" and "stone" in commit messages and notes refer to the weekly rows of the phase 1 table in the plan.

## The notes, one line each

| File | What it is |
|---|---|
| `notes/nordcast-plan.md` | What gets built, in what order, and the gate that unlocks each phase |
| `notes/preregistration.md` | Binding. The test a challenger must pass before it becomes the headline call, fixed before the test began |
| `notes/incidents.md` | Every missed window and job failure, with cause and fix |
| `notes/sources.md` | The data register: each Energinet dataset, its columns, units and sign, and the sign checks |
| `notes/inception.md` | The first available row of each dataset and where the backfill started |
| `notes/replay.md` | How the rehearsal works: the ladder of methods and the rule for promoting one |
| `notes/replay-log.md` | The rehearsal's results, round by round, with the reviews |
| `notes/controls.md` | The controls the other notes cite by section number |
| `notes/limits.md` | The simulated trading limits: 10 MW, EUR 5,000 a day, flat on breach |
| `notes/backfill.md` | How history was loaded with estimated publication times |
| `notes/data-alternatives.md` | Other data sources considered and why they were not used |
| `notes/from-energy-forecasting.md`, `notes/source-repo-context.md` | What was carried over from the sister project, energy-forecasting |
| `notes/models/*.md` | Model cards for the LightGBM direction and volume models |
| `notes/later/*.md` | Designs for phases 2 to 4, parked until their gate opens |
| `notes/scenarios.yaml` | The stress scenarios used in the risk layer |

## The replay

`replay/` holds the rehearsal: four quarterly rounds from Q4 2025 to Q3 2026. Each round has a plan (which methods run), a scorecard, diagnostics and a review. Each round adds one method to the ladder; the method with the lowest mean pinball loss over the three horizons wins the round and becomes the model for the next. The replay uses estimated data vintages, so it flatters every method a little and is never mixed with the live record.

## The analysis layers

`docs/layers/` holds side studies built on the record, each with its own README and a risk note written before the code. They are numbered after the sister project's catalogue (for example "Layer #32"). Each ends with a verdict on whether it adds forecasting value; most do not, and say so.

## The jobs

Three launchd agents on one Mac, installed by `ops/install.sh`:

- `nordcast.archive`, every minute: pull the live feeds into the archive repository.
- `nordcast.jobs`, every minute: load, freeze, score; after midnight Copenhagen time, timestamp the day and rewrite the README scorecard; hourly, push a heartbeat and back up the database.
- `nordcast.stack`, at login: start Colima and the local Supabase stack.

Only the jobs push to GitHub, and only their own commits (heartbeat, stamp, scorecard). A GitHub Actions workflow (`.github/workflows/deadman.yml`) alerts if the heartbeat stops.

## The sister repositories

- `nordcast-archive` (private): raw daily Parquet files from the live feeds, appended every minute. Not written for reading.
- `nordcast-backups` (private): hourly database dumps for disaster recovery.
- `energy-forecasting`: the sister project this one was scaffolded from, a weekly crude-oil forecasting record with the same freeze-and-score design.
