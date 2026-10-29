# incidents

one entry per incident, per controls.md §5: date, detected by, what broke, record impact, root cause, fix, prevention. missed calls are scored as misses on the public scorecard, with a footnote here.

## 2026-10-28/29 – no live freezes; archive down overnight

- **detected by:** me, at the start of the 29 oct session (no deadman existed yet).
- **what broke:** (1) `nordcast.jobs` was never loaded: `ops/install.sh` wasn't run at the end of step 3, so persistence was frozen only by hand during the build, the last time at 19:26 utc 28 oct. (2) the mac restarted overnight (up 5 min at 06:15 utc 29 oct) and `nordcast.archive` didn't come back: its plist is in ~/Library/LaunchAgents but launchd had no service by that name at 06:15 utc. last archive pull 21:32 utc 28 oct; the agent was running again at 06:22 utc 29 oct, apparently loaded late after login.
- **record impact:** the record hadn't started: no isp had a scheduled live freeze before the install, so nothing is scored as a miss. the archive lost ~8.8 h of first-print timing. a one-off pull at 06:19 utc 29 oct refilled `PowerSystemRightNow`, `ElectricityProdex5MinRealtime`, `ImbalancePrice`, `MfrrEnergyActivationMarket` and `mfrrRequest` (from its 7-day window) for 21:00–06:19 utc, stamped with that pull's `pulled_at_utc`, so those rows are late vintages, not first prints. `Forecasts_5Min` revisions issued in the gap are gone (the server overwrites them).
- **root cause:** launchd agents installed only by hand, with nothing checking that they ran.
- **fix:** none running yet; see the next entry. step 6 adds the heartbeat (`jobs/heartbeat.py`, hourly push of `status/heartbeat.json`) and the deadman on github (`.github/workflows/deadman.yml`: fails when the heartbeat is over 75 min old, its last freeze was over 20 min old or its last `mfrrRequest` pull over 15 min old).
- **prevention:** the deadman. the 7-day soak counts from the install, not from this entry.

## 2026-10-29 – agents removed, record run by hand

- **detected by:** me.
- **what happened:** at ~06:30 utc another claude session on this mac ended the step 6 session, misreading "close the other sessions"; nothing in the repo changed after 06:26 and the session resumed. after that, at my request, every nordcast launchd agent (archive, jobs, stack) was removed with `ops/uninstall.sh`: no background agents on the machine for now. the jobs are run by hand.
- **record impact:** the record isn't running. no live freeze, score, heartbeat or archive pull happens unless run by hand, so `mfrrRequest` (7-day window) and the `Forecasts_5Min` revisions age out between runs, and first-print timing is only as good as the last manual pull. nothing scheduled is scored as a miss because no schedule has started; the 28 oct hand freezes stand as they are. the challenger's preregistered window can't open.
- **root cause:** a decision, not a fault: background agents are off on this machine until further notice.
- **fix / what the 7-day soak needs:** the jobs on a clock for 7 days running: `ops/install.sh` (archive every minute, jobs every minute, stack at login), or the same on another always-on host. then the deadman pushed and green, and the soak report (on-time rate from `status/heartbeat.json` and `jobs/scorecard.py`) here.

## 2026-10-29 – record started; one window missed; a challenger row took a headline call down

- **detected by:** me (log and record read at 19:22 and 19:31 utc); the challenger failure by the energy-forecasting session.
- **what happened:** (1) the agents were installed at 18:58 utc with `ops/install.sh` (my call: agents on, replacing the morning's entry above). at 19:00:40 all three were unloaded, with no launchd log entry and the plists left in place; not by this session or the one that installed them, cause unknown. they were loaded again by 19:22. (2) at 19:26 and 19:27 the freeze for 20:00 at 30 min failed whole: `make_row` rounded the challenger's three probabilities separately, they missed 1 by more than the `forecast_probabilities` check's 0.0001, and the isp's rows share one transaction, so the headline went down with it. (3) the challenger's first calls (18:55, all horizons) raised MissingData: every row the restarted archive loaded at 18:58 is published at 18:58, after the challenger's asof (isp − h − 5 min).
- **record impact:** headline misses: 19:30 at 15 min, 19:45 at 30 min, 20:15 at 60 min (the whole 19:10–19:15 window). 20:00 at 30 min froze at 19:28, inside its window, after the fix: on time. challenger misses: 19:15/h15, 19:30/h30, 20:00/h60 (18:55) and the same three as the headline. all scored as misses.
- **root cause:** (1) unknown. (2) per-probability rounding against a sum check, and a challenger row inside the headline's transaction. (3) expected after any archive gap: data loaded late is late.
- **fix:** (2) `3f8737f`: p_none is the remainder of the rounded p_up and p_down; each challenger row in its own savepoint. (1) watched by the deadman once the heartbeat is pushed.
- **prevention:** the soak counts from 19:22 utc 29 oct, the reload.
