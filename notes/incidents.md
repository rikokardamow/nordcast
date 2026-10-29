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
