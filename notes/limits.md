# limits – written before any position

29 oct 2026, per controls.md §7. **adopted 29 oct 2026: the owner told claude code to take the practical decisions, and these are the proposals it made, unchanged. a limit changes only by the owner, with a change log line, never intraday.** every position in nordcast is simulated ("would have"); the limits still come first, so the backtests are run under them, not fitted around them.

## strategy: hold-into-imbalance (L1/L2)

| limit | value | action on breach |
|---|---|---|
| max position | 10 mw, either direction (the stated size; positions are in [−1, 1] × 10 mw) | a larger position is a bug: the build raises |
| per-isp exposure | 2.5 mwh (10 mw × 15 min) | – |
| daily loss limit | €5,000 per copenhagen day, realised at first-print imbalance prices | flatten from the next isp to the end of the copenhagen day; log the breach with the isp, the loss and the conditioners |
| stale feed | the target's latest known isp one isp older than usual for the horizon | position capped at 0.25 (2.5 mw) for that isp |
| stale feed, longer | two or more isps older than usual (~30 min without fresh prints) | no position (from 29 oct 2026; before that, capped) |
| missing call | no frozen call for the isp and horizon | no position: never a substituted one |

why €5,000: at 10 mw a 15-min isp risks 2.5 mwh, so €5,000 is 2,000 €/mwh of adverse spread in a day: about twenty isps against the call at the ~100 €/mwh spreads that are common in dk1, or two or three at the scarcity spreads of 4 mar – 1 jun 2025. it binds on bad days and not on ordinary ones.

why flatten after 30 min: the l3 stress (notebooks/12_risk.ipynb) held a capped position through a 2 h outage under the old rule and lost eur 4,419, inside the daily limit by little; with no prints arriving the loss limit itself can't act. flattening ends the exposure the limit can't see.

## who changes a limit

the owner only, with a dated line in CHANGELOG.md saying old value, new value and why, effective from the next copenhagen day. never intraday, never after looking at that day's pnl.
