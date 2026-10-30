# controls – the same in every repo

28 oct 2026. the templates behind portfolio-plan.md's seven points. copy into each repo's notes/ and fill in. short on purpose: if a control takes more than ten minutes a week, it won't survive.

## 1. data register (`notes/sources.md`)

one row per source, filled before the first pull:

| field | example (nordcast) |
|---|---|
| source / dataset | energinet energi data service / PowerSystemRightNow |
| endpoint | api.energidataservice.dk/dataset/PowerSystemRightNow |
| licence | cc by 4.0 |
| republish raw? | yes, with attribution |
| attribution text | "data: energinet, energi data service" |
| cost | 0 |
| rate limit | per-dataset, http 429; back off 60 s |
| history start | (from the inception probe) |
| revision behaviour | first print kept; revisions as new vintages |
| known breaks | 4 mar 2025, 2 jun 2025, 1 oct 2025, mari (q1 2027) |
| verified on | date + how (browser / api / test) |

a source with "republish raw? no" (ice, cme via databento, eex, consensus articles) never reaches `site/`, `docs/` or the public repo; a ci check greps the public tree for its series ids.

## 2. model card (`notes/models/<model>.md`)

```
model:          lightgbm-volume-v1
call:           dk1 imbalance volume q10/q50/q90, 15/30/60 min
status:         challenger since <date> | headline since <date>
inputs:         <series ids>, all read through value_asof
training:       <window>, refit weekly, hyperparameters chosen inside the window
assumptions:    <list>
known limits:   <regimes it hasn't seen; e.g. mari>
pretraining:    n/a | <cutoff> for foundation models
validation:     notes/validation/<file>, result
version:        <git sha of model code> + <hash of artefact>
changes:        <dated list>
```

## 3. validation checklist (`notes/validation/<model>-<date>.md`)

run in a fresh claude code session that hasn't seen the build, given only the model card, the code path and the scorecard export:

- does every feature read through value_asof with asof ≤ freeze time? (run the leakage test)
- is the training window strictly before the scoring window? are hyperparameters chosen inside it?
- does the score beat the incumbent over the pre-registered window, with the bootstrap interval reported?
- coverage of q10–q90 within 70–90 % on the window? by hour / regime?
- what are the ten worst misses and is there a pattern the card doesn't mention?
- anything in the code that substitutes a missing input instead of failing?
- verdict: promote / keep as challenger / retire, with one paragraph why.

I read it, agree or disagree in writing, and only then change the headline call, at a quarter boundary.

## 4. change log (`CHANGELOG.md`)

one line per change that touches the record: date, what, why, model card diff link, hashes of affected frozen files. data-source changes too (energinet renames a column → a line here and an incident).

## 5. slos and the incident log (`notes/incidents.md`)

| repo | slo | measured as |
|---|---|---|
| nordcast | on-time freeze ≥ 99 % of isps × horizons | rows frozen before scheduled_at / rows due |
| gasbook, wpsr | 100 % of weeks | freezes before release |
| all | first-print capture ≤ 30 min after publication | pulled_at − published |

incident entry: date, detected by (health check / daily tests / me), what broke, record impact (how many calls missed or late), root cause, fix, prevention. missed calls are scored as misses on the public scorecard, with a footnote to the incident.

## 6. published kpis (scorecard page header)

- skill vs headline baseline: mean improvement in the pre-registered loss, bootstrap 90 % interval
- coverage of stated bands
- on-time freeze rate
- incidents this quarter
- sample size

## 7. limits (`notes/limits.md`, before any L1 position)

per strategy: max position, daily loss limit, the action on breach (flatten next period, log), and who can change a limit (me, with a change log line, never intraday). simulated or not, written first.
