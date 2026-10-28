# Context Briefing – energy-forecasting (source of the record machinery)

Read at commit `db13eb1` (28 Oct 2026). nordcast and gasbook copy from this; they don't import it.

## Tech Stack
- **Language**: Python 3.12 (`.python-version`), package `energy_forecasting`, build backend `uv_build >=0.13.5,<0.14`, env and lock via uv
- **Database**: Supabase Postgres, **local** (`supabase start`, `127.0.0.1:44322`), 11 migrations in `supabase/migrations/`
- **Runtime**: macOS launchd on the Mac mini (`ops/launchd/energy.jobs.plist` → `ops/run_jobs.sh` every 30 min; `energy.awake.plist` keeps it awake). GitHub Actions runs only `deadman` (every 30 min Mon–Fri) and `tests`; the freeze/score workflows exist but are `workflow_dispatch` only
- **Site**: Next.js (app router) + `@supabase/supabase-js` with the anon key, ECharts themed from CSS tokens, vitest, pnpm; Vercel
- **Key deps**: httpx ≥0.28.1, pandas ≥3.1.0, psycopg[binary] ≥3.3.6, opentimestamps 0.4.5 / client 0.7.2; dev: pytest ≥9.1.1, ruff ≥0.17.2, vcrpy ≥9.2.0; groups `models` (timestral from git, pinned HF revision) and `reports` (ipykernel, matplotlib, nbconvert, papermill)
- **Auth**: none for jobs (local db); site reads through RLS with the anon key

## Directory Structure
```
src/energy_forecasting/   library: store (hub), freeze, score, baselines (leaf), calendar,
                          schedule, ingest, quality, stamp, runlog, deadman, backup,
                          backtest, consensus, timestral_model, runreport, review, streak, posts, site
  sources/eia.py          one fetch() with retries + key scrubbing + raw JSON saved; to_observations()
jobs/                     thin entry points: freeze_wpsr, score_wpsr, pull_eia, seed_releases,
                          stamp_frozen, verify_freeze, capture_consensus, backtest_wpsr, deadman, backup…
supabase/migrations/      source/series, release, observation, value_asof, forecast, score,
                          web views, crude balance, run_log, challenger, web card baseline call
forecasts/frozen/         one JSON per release + .ots proof, committed
ops/                      launchd plists, run_jobs.sh, install/uninstall
site/                     Next.js read-only dashboard
tests/                    fresh DB from migrations per session, rollback per test, vcrpy cassettes
docs/                     DESIGN (review), PRD, STEPS (stepping stones), Architecture, PROJECTS, REPOS…
PARKING.md                ideas not in spec: date | idea | result that would justify it | where it joins
```

## Architectural Patterns
- **Record, not platform.** One scored series (WPSR crude change). Layers unlock by streak health, not calendar.
- **Insert-only store.** Triggers refuse UPDATE/DELETE/TRUNCATE on observation, forecast, score. A revision is a new observation row with a later `published_at`.
- **One read path.** `value_asof(series, period date, asof timestamptz)` — SQL function, latest vintage with `published_at <= asof`. Baselines, models, scorer, backtest all go through it. Called **one period at a time** from Python.
- **The database decides the clock.** `forecast_before_release` sets `frozen_at := now()` and raises if `now() >= release.scheduled_at`. `release.scheduled_local` + `tz` → `scheduled_at` by trigger, so DST is the database's problem.
- **Cron only wakes jobs.** `schedule.due_for_freeze` picks the release 12–36 h ahead with no model row; `due_for_score` picks due, frozen, unscored releases in the last 14 days. Jobs are idempotent and safe to run every 30 min.
- **Fail to a flagged baseline, never to nothing.** Model failure → seasonal naive frozen with `status='auto_baseline'`; EIA down → `pull_or_stale` gives a blocking gate and the freeze still happens on stored data. Challengers never block.
- **Proof outside the repo.** Each frozen file gets an OpenTimestamps `.ots` (Bitcoin-anchored), verified by `stamp.check`; stamping never blocks.
- **Backup off the machine.** `backup.run()` after every write: plain-SQL dump + manifest + `data/raw/` into a private backups repo, committed (git history is retention).
- **Site never imports Python.** Reads `web_*` views; `site.notify()` POSTs `/api/revalidate`; pages also revalidate every 5 min.

## Data Model
| Entity | Key fields | Relationships |
|---|---|---|
| source | source_id, **licence_class (open/derived/restricted)**, licence, attribution | 1→n series, release |
| series | series_id (`eia.wcestus1`), code, unit, **frequency ∈ daily/weekly/monthly/quarterly/annual** | n→1 source; 1→n observation |
| release | release_kind, **period_end date**, scheduled_local, tz (default America/New_York), scheduled_at (trigger), **basis ∈ eia_schedule/rule**, status | unique (release_kind, period_end); 1→n forecast |
| observation | series_id, **observed_for date**, value numeric, published_at, ingested_at, payload_hash (trigger), vintage_quality exact/estimated | unique (series_id, observed_for, payload_hash) |
| forecast | release_id, series_id, target_period date, source_kind model/baseline/consensus/challenger, method, status frozen/auto_baseline, point, q10/q50/q90, data_cutoff, model_version, sha256, payload jsonb | **unique (release_id, source_kind, method)**; 1→1 score |
| score | forecast_id unique, actual, error, abs_error, first_print_at, outlier, status scored/eia_delayed/revised_after | n→1 forecast |
| run_log | job, started_at, outcome ok/nothing_due/failed, detail | – |
| web_* views | cards, crude balance, baseline call | read by the anon role; licence_class filter |

```
source ─< series ─< observation ──(value_asof)──► baselines / model / scorer
source ─< release ─< forecast ─── score
```
RLS is enabled on every table with no policies: only the views are readable from the browser.

## Conventions
1. Series ids lowercase dotted by source: `eia.wcestus1`, `eia.cushing`.
2. Baselines and models take a `read(series_id, period, asof)` callable, not a connection (`baselines.seasonal_naive(value_asof, series_id, week, asof)`), so backtests run without a database.
3. Model functions return a dict `{point, q10, q50, q90, model_version, …}`; `freeze.make_row` canonicalises it to JSON (sorted keys, numbers as `"%.1f"` strings) and sha256s it.
4. Missing data raises (`baselines.MissingData`); nothing is substituted silently.
5. Jobs are thin, the library holds logic; every job is wrapped in `runlog.logged(...)` on its own connection.
6. API keys never appear in errors, URLs in logs, or saved raw files (`eia._scrub`).
7. Tests build a fresh database from the migrations each session and roll back each test; network calls replay from cassettes.
8. Docs use the "rules that never bend" list in STEPS.md; PARKING.md holds every idea that isn't in the spec.

## Infrastructure Constraints
- The record depends on the Mac being on: launchd + local Postgres. Deadman on GitHub catches a missing freeze because frozen files are pushed to the public repo.
- A freeze is a git commit; a 30-min loop is the finest cadence the current runner was designed for.
- `make_row` formats numbers to one decimal (`"%.1f"`) before hashing – fine for kb/d, wrong for MW-level or Bcf-level precision choices you want to keep.
- `freeze.freeze` refuses if `forecasts/frozen/<kind>-<period>.json` exists: one file per release by design.
- `backup` dumps whole tables as SQL into git; fine at weekly volume, not at 5-minute volume.
- STEPS rules: at most one layer in progress plus two passive recorders; design capped at 20 % of hours; only open/derived data on pages; no AI features in the product.

## Integration Points
| Service | Purpose | Auth |
|---|---|---|
| EIA API v2 | WPSR series | API key in query string, scrubbed |
| OpenTimestamps calendars + blockstream.info | timestamp proofs, block-time check | none |
| GitHub | public record (frozen files), deadman and tests CI, private backups repo | git credentials on the Mac |
| Supabase (local) | the record | local postgres password |
| Vercel | site | Supabase URL + anon key; REVALIDATE_SECRET |
| Hugging Face | Timestral weights, pinned revision | none |

## Warnings / Tech Debt (what the new repos must not assume)
- `value_asof` is per-period and date-typed; a 15-min target needs a timestamptz version and a **bulk** history read, or a 2048-step challenger context costs 2048 queries per call.
- `freeze.make_calls`, `seasonal_model`, `score_release` and `baselines` are written around **weekly changes of a level**. gas storage's target is EIA's reported net change, which is not always the level difference (reclassifications); score against the reported net change series.
- `release` has no horizon concept and `forecast`'s unique key has no horizon column.
- `series.frequency` and `release.basis` checks don't allow 5-min/15-min/hourly or ISP schedules.
- The roadmap in STEPS.md schedules "US gas storage (Thursday)" and "power (Ireland/GB)" as forecast tracks inside this repo in 2027. If gasbook and nordcast own those records, edit STEPS.md and PROJECTS.md so the same call isn't built twice.
