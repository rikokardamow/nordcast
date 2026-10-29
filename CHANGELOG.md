# change log

one line per change that touches the record or its limits (controls.md §4): date, what, why, link.

- 2026-10-29 · **limits:** a feed stale by two or more ISPs now means no position (was: capped at 2.5 MW). Why: the L3 stress showed a capped position held through a 2 h outage losing EUR 4,419 with the daily limit unable to act on missing prints. notes/limits.md, src/nordcast/positions.py. Decided by Claude Code on the owner's instruction to take the practical decisions; effective for every simulated position from 30 Oct 2026 (the next Copenhagen day).
- 2026-10-29 · **pre-registration, amendment 1:** the direction test must also beat `direction_climatology`, not only persistence (whose one-hot probabilities any calibrated model beats). Stricter; made before the window opened. notes/preregistration.md, docs/experiments/direction-bar.
