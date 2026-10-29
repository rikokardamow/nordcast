# incidents

one entry per incident, per controls.md §5: date, detected by, what broke, record impact, root cause, fix, prevention. missed calls are scored as misses on the public scorecard, with a footnote here.

## 2026-10-28/29 – no live freezes; archive down overnight

- **detected by:** me, at the start of the 29 oct session (no deadman existed yet).
- **what broke:** (1) `nordcast.jobs` was never loaded: `ops/install.sh` wasn't run at the end of step 3, so persistence was frozen only by hand during the build, the last time at 19:26 utc 28 oct. (2) the mac restarted overnight (up 5 min at 06:15 utc 29 oct) and `nordcast.archive` didn't come back: its plist is in ~/Library/LaunchAgents but launchd had no service by that name at 06:15 utc. last archive pull 21:32 utc 28 oct; the agent was running again at 06:22 utc 29 oct, apparently loaded late after login.
- **record impact:** the record hadn't started: no isp had a scheduled live freeze before the install, so nothing is scored as a miss. the archive lost ~8.8 h of first-print timing. a one-off pull at 06:19 utc 29 oct refilled `PowerSystemRightNow`, `ElectricityProdex5MinRealtime`, `ImbalancePrice`, `MfrrEnergyActivationMarket` and `mfrrRequest` (from its 7-day window) for 21:00–06:19 utc, stamped with that pull's `pulled_at_utc`, so those rows are late vintages, not first prints. `Forecasts_5Min` revisions issued in the gap are gone (the server overwrites them).
- **root cause:** launchd agents installed only by hand, with nothing checking that they ran.
- **fix:** `! ~/nordcast/ops/install.sh` (loads archive, jobs and stack; `nordcast.jobs` was still not loaded at 06:25 utc). step 6 adds the heartbeat (`jobs/heartbeat.py`, hourly push of `status/heartbeat.json`) and the deadman on github (`.github/workflows/deadman.yml`: fails when the heartbeat is over 75 min old or its last freeze was over 15 min old).
- **prevention:** the deadman. the 7-day soak counts from the install, not from this entry.
