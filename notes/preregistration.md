# pre-registration – DK1 imbalance calls

**status: draft, 29 oct 2026. becomes binding when committed with "Pre-register" in the message, before the challenger's first scored day. after that it changes only by a dated amendment below, never by an edit.**

**open, mine to decide before committing:**
1. **the bar.** the plan: lightgbm takes the call by beating persistence. notes/replay.md: the live model starts from the replay's winner, ar(1), which was ~20 % better than persistence on every horizon in round 4. this draft asks for both (the "second condition" below). alternatives: persistence only (plan as written), or ar(1) as the bar and the headline from now.
2. **the window.** this draft: the challenger's first 60 full days (nordcast-plan.md, 28 oct). the earlier PROMPT said 30. with the record started by early december, 60 days closes in february, still before the 1 apr 2027 boundary; 30 doesn't move the earliest promotion.
3. the window can only open once the jobs run on a clock (notes/incidents.md, 29 oct).

## the call

- **target, volume:** `ImbalancePrice.SatisfiedDemand`, DK1, MW, + = up regulation (system short), per 15-min ISP. sign checked in `tests/test_sign_convention.py`.
- **target, direction:** `ImbalancePrice.DominatingDirection`, DK1: up / down / none.
- **scored against:** the first print of each (the earliest `published_at` in the record). later revisions are kept, never rescored.
- **horizons:** 15, 30 and 60 min before the ISP starts, frozen in the 5 min before ISP start − h (`schedule.due_for_freeze`). a call not frozen in its window is a miss.

## what's frozen

| source_kind | method | role |
|---|---|---|
| model | model | the headline. `v0-persistence` until a promotion under this file |
| baseline | persistence | the bar |
| baseline | persistence_ar1 | the replay's winner (notes/replay-log.md) |
| baseline | direction_climatology | direction by Copenhagen hour, 28 days |
| challenger | lightgbm_v1 | LightGBM v1, artefacts by sha256 in `data/models/manifest-lightgbm-v1.json` (h15 `db327da0b1b4…`, h30 `c9ecf0d189d7…`, h60 `a067374958c4…`); fed only what training could see (`challenger.nominal`) |

## the test

- **window:** the challenger's first 60 full Copenhagen days live, counted from the first day on which it froze every ISP at 15 min. no peeking rule is needed because nothing is decided before the window closes; the scorecard shows the running numbers anyway.
- **primary horizon:** 15 min. 30 and 60 min are reported, not tested.
- **losses:** volume, mean pinball over q10/q50/q90; direction, the multiclass Brier score. both as in `nordcast.score.losses`.
- **misses:** a challenger call that wasn't frozen is filled with the persistence call for that ISP, so a miss can never help it. an ISP the headline missed is dropped for both (the comparison needs the bar).
- **statistic:** per ISP, d = loss(persistence) − loss(challenger); averaged per day; a day-block bootstrap (resample days with replacement, 10,000 draws, seed 20261029) of the mean daily d. **pass** when the 90 % interval (5th–95th percentile) is above zero, for pinball and for Brier, each on its own.
- **second condition:** on the same window and bootstrap, the challenger's pinball is not worse than `persistence_ar1`'s (the 90 % interval of loss(ar1) − loss(challenger) doesn't sit wholly below zero). beating persistence alone is easy; the replay showed ar(1) ~20 % better.

## after the test

- **independent validation:** a fresh session with none of the build's context runs controls.md §3 on the challenger: code read, no-leakage test, re-score from the stamped daily files, the model card. its note goes in notes/models/. no promotion without it.
- **promotion:** only at a quarter boundary, the first one after the window closes and validation is written. earliest 1 apr 2027. the change log gets a line, the model card's status changes, and the old headline stays frozen as a baseline.
- **fail:** the challenger stays a challenger; a v2 gets its own pre-registration and its own window. no re-running this test on a different window.
- **regime break:** MARI accession (target q1 2027) or a change to the `SatisfiedDemand` definition stops the window. what was scored is reported; the test restarts after a retrain, with an amendment here.

## reported beside the test, not tested

coverage of q10–q90 (target 80 %), direction accuracy, MAE, the hold-into-imbalance P&L (10 MW in the called direction, settled at the first-print imbalance price vs day-ahead), on-time freeze rate.

## amendments

none yet.
