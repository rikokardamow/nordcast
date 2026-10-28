# what to take from energy-forecasting

28 oct 2026, re-read at commit db13eb1 (see source-repo-context.md for the full map). supersedes the earlier version of this file. both new repos copy the record machinery and change it where the code is built around a weekly crude change; neither imports energy-forecasting, and the three records stay separate.

## what the code actually does (and the earlier notes got wrong)

- **it runs on the mac, not github actions.** freeze, stamp, score, pull and backup run from launchd every 30 min against a local supabase. actions runs only the deadman and the tests. the earlier plans put nordcast on actions cron every 5 min against a cloud database; actions cron routinely starts late, which would break a 99 % on-time target by itself. both new repos run on the mac mini the same way, with their own launchd jobs.
- **`value_asof` is one period at a time.** fine for weekly; for nordcast, 12 lags × several series × 3 horizons every 5 min, and a 2048-step challenger context, it's thousands of queries. needs a bulk read.
- **the scorer computes "change in a level".** gas storage's target is eia's reported net change, which differs from the level difference in reclassification weeks.
- **`make_row` rounds to one decimal before hashing.** fine for kb/d and for bcf; nordcast keeps one decimal for mw too, but probabilities need four.
- **a freeze is a file and a commit.** one json per release, refused if it exists. right for gasbook (52 a year); 96 isps × 3 horizons a day for nordcast is not.
- **backup dumps whole tables into git.** right at weekly volume, wrong for 5-min rows.
- **the roadmap in STEPS.md already plans "us gas storage (thursday)" and "power (ireland/gb)" as tracks in this repo for 2027.** gasbook and nordcast take those over: edit STEPS.md's table and PROJECTS.md #20 when gasbook starts, so the call isn't built twice.
- **the rules in STEPS.md apply to the new repos too:** one layer in progress plus two passive recorders; baselines-only live for the first weeks; model swaps only at quarter boundaries; only open or derived data on pages.

## gasbook – nearly a straight copy

copy verbatim, renaming the package: `store`, `freeze`, `score`, `schedule`, `runlog`, `quality`, `stamp`, `deadman`, `backup`, `ingest`, `consensus`, `runreport`, `sources/eia.py`, the 11 migrations, `tests/conftest.py`, `ops/` (new launchd labels), `.github/workflows/deadman.yml` and `tests.yml`, `jobs/` for freeze/score/stamp/verify/backup/deadman/capture_consensus.

change:
- `calendar.py` → `wngsr_releases()`: thursday 10:30 new york, alternate dates from `ir.eia.gov/ngs/schedule.html` as the `EIA_ALTERNATE_DATES` dict with a "checked on" date and `EIA_SCHEDULE_COVERS_TO`, rule-based beyond it (thanksgiving → wednesday 12:00, christmas/new year weeks as the page shows). same tests as the wpsr calendar.
- seed migration: `source` rows for eia (open), gie (open, attribution "GIE AGSI+"), noaa cpc (open); later databento/ice as `restricted`. `series` rows for the l48 net change, the l48 level, the five regions, implied flow, hh spot.
- the target is the **reported net change series** (`eia.ng.l48.netchange`), observed_for = week ending friday. `score_release`'s `change()` is replaced by a direct `value_asof(target, week, first_print_at)`; the level stays a feature.
- reclassification: a `reclass` flag series from wngsr.json; `score` gets `reclass_week boolean` and `within_tolerance boolean` (|error| ≤ 0.8 bcf) in one migration.
- `baselines.py`: keep `weekly_change` and the shape; `seasonal_naive` over the net-change series, 5 years, 2020 **included** (gas wasn't distorted the way crude was; write it in the model card); `last_four_weeks` unchanged.
- `freeze.make_calls` unchanged; the default `seasonal_model` becomes the gas one.
- `site/` later, copied whole when the gate opens.

## nordcast – the machinery copied, three pieces rewritten

copy verbatim: `runlog`, `quality` (Gate), `stamp`, `deadman` (logic), `backup` (logic), `consensus` (unused for now), the test fixture, `ops/` shape, deadman and tests workflows, the migrations as a starting point.

### schema (one migration on top of the copied ones)
- `observation.observed_for`, `forecast.target_period`, `release.period_end` → `timestamptz`. `value_asof(text, timestamptz, timestamptz)`.
- `series.frequency` check adds `'5min'`, `'15min'`, `'hourly'`. `release.basis` adds `'isp'`; `release.tz` default `'Europe/Copenhagen'`.
- `forecast`: `horizon_min int not null`, in the unique key `(release_id, source_kind, method, horizon_min)`; `direction text check in ('up','down','none')`, `p_up`, `p_down`, `p_none numeric`.
- `score`: `direction_actual`, `direction_hit`, `brier`, `pinball_q10`, `pinball_q90`, `covered`; status values `scored`, `print_missing`, `revised_after`.
- a bulk read: `history_asof(series text, from_ts timestamptz, to_ts timestamptz, asof timestamptz) returns table(observed_for timestamptz, value numeric)` – latest vintage per period with published_at ≤ asof, one query (`distinct on (observed_for) … order by observed_for, published_at desc`). a test asserts it equals looping `value_asof`. features, baselines and challengers use it.

### what lives where
- postgres holds the **15-min isp level**: the target, the features actually used, energinet's forecasts, prices, dmi point values per run. ~150 rows per series per day.
- the **5-min raw** feed and dmi grib stay in the archive repo as daily parquet partitions, with pulled_at. the isp aggregate is computed from it and inserted as observations with published_at = the pull time of the last 5-min row in the isp.
- backup dumps the postgres record (manageable at isp level); the archive repo is its own backup.

### freeze, stamp, score
- `release` rows: one per isp (`release_kind='dk1_isp'`, period_end = isp start, scheduled_local = isp start − 1 min in copenhagen time, basis `'isp'`). the existing trigger then refuses any call after delivery starts, with no code.
- `schedule.due_for_freeze` rewritten: for each horizon h, isps whose start is in [now + h, now + h + 5 min] with no model row for that horizon.
- `freeze.freeze` split in two: `freeze_rows()` writes the rows (transaction, sha256 per row, same `make_row` with probabilities at 4 decimals) and **no file**; `jobs/stamp_daily.py` at 00:10 copenhagen writes `forecasts/frozen/dk1-<date>.json` with every row of the day, its sha256, an `.ots`, one commit, one push. per-row hashes in the db, the daily file is the public proof.
- `score_release` rewritten for levels: actual = 15-min mean from the first prints covering the isp; direction from the first `ImbalancePrice.DominatingDirection` vintage.
- launchd: `nordcast.jobs.plist` every 1 minute (`StartInterval 60`) running `ops/run_jobs.sh`: pull real-time (5-min feed, mfrrRequest), freeze what's due, score what's out. dmi pull every 15 min inside the same script. the job is idempotent; a 60 s loop gives a 5-min freeze window enough slack.
- deadman on github: the mac pushes `status/heartbeat.json` (last freeze time, last score time, on-time rate) every hour; the action fails if it's older than 75 min or the last freeze is older than 15 min at push time.

### baselines and models
- new `baselines.py`: `persistence(history, isp, h)`, `persistence_ar1`, `direction_climatology(hour)`. same `MissingData` discipline, but they take the bulk `history` callable.
- the timestral challenger file is the pattern for chronos/timesfm/timestral: pinned revision, `context_steps` recorded, raise below minimum context, read through `history_asof` (one query, not a loop).
- `freeze.make_calls` keeps its contract: model failure → flagged persistence; challengers never block.

## leave, in both

`backtest.py` and `jobs/backtest_wpsr.py` (write the replay fresh), `posts.py`, `review.py`, `streak.py` (copy later if the weekly routine needs them), `site/` until its gate.
