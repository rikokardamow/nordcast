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

## 2026-10-29/30 – mac off overnight, agents didn't come back: 21.9 h down

- **detected by:** the deadman on github (failing from 23:54 utc 29 oct; github ran it about every 6 h, not every 30 min), and me at 19:54 utc 30 oct.
- **what happened:** the last run was 22:14 utc 29 oct; the mac slept and shut down. it rebooted at 06:17 utc 30 oct, shut down at 06:48, and rebooted at 19:43. the three plists stayed in `~/Library/LaunchAgents`, but launchd hadn't loaded them after either reboot, though i logged in at 19:44. restored by `ops/install.sh` at about 20:01. first calls back: 20:10:59 utc, headline and challenger, all horizons.
- **record impact:** of 264 headline calls due between 22:14 utc 29 oct and 20:05 utc 30 oct, 3 were frozen and **261 were missed**, all scored as misses. the challenger missed the same. the 7-day soak from 29 oct is void; it counts from 20:01 utc 30 oct, so the report is due after 20:01 utc 6 nov. g1 can't be met on 28 nov: 30 clean days from 31 oct end on 29 nov. the challenger's window can open on 31 oct at the earliest, closing 29 dec. a one-off pull at 20:01 utc 30 oct refilled `PowerSystemRightNow`, the 5-min feed and `mfrrRequest`; `ImbalancePrice` and mfrr activation needed nothing. refilled rows carry that pull's `pulled_at_utc`, so they're late vintages, not first prints. `Forecasts_5Min` revisions from the gap are gone.
- **root cause:** (1) power settings: `sleep 1`, `autorestart 0`. (2) why the agents didn't load at login: not found. they aren't in launchd's disabled list and the system log has no entry for them; macOS's login-items setting is unchecked. (3) no auto-login, so agents can't start after a reboot until someone logs in.
- **fix:** agents reinstalled. **not fixed:** `sudo pmset -a sleep 0 autorestart 1` still needs the owner's password, and a reboot would still stop the record.
- **prevention:** the pmset change, the login-items check, then one deliberate reboot to prove recovery. if the soak misses again, move to an always-on host.
- **30 oct, later:** `nordcast.jobs` was unloaded again between 20:19 and 20:21 utc, plist in place, no log entry, no install running; cause unknown. reloaded by hand at 20:21, before the next window, so no call was missed. added `ops/watchdog.sh` (agent `nordcast.watchdog`, every minute): reloads a lost agent and logs the time to `~/Library/Logs/nordcast/nordcast.watchdog.log`. it can't stop a reboot or restart anything before login. the pmset change hadn't taken effect at 20:31.
- **30 oct, later still:** github workflows are off (the owner's rule: github is repo and commits only), so the deadman no longer runs. the health check moved to this mac: `status/heartbeat.json` every 5 min, not committed, with a log line and a notification when freezes or pulls go stale. nothing alerts if the mac itself is off. the watchdog was also found unloaded at 21:05 and reloaded by hand.

## 2026-10-30/31 – mac slept, then restarted, agents didn't come back: 10.2 h, 114 calls missed

- **detected by:** me, at 07:35 utc 31 oct, while doing other work. the local health check logged the stale freezes before the restart, but nothing off the mac could report it.
- **what happened:** the mac went into sleep cycles from about 21:20 utc 30 oct, so the jobs ran only in brief wakes: one freeze at 23:10, last run 23:22. it rebooted at 07:23 utc 31 oct and launchd hadn't loaded the agents, the same failure as 29/30 oct. colima and supabase were up. `ops/install.sh` at 07:36; first freeze 07:40.
- **record impact:** of 132 headline calls due from 20:30 utc 30 oct to 07:40 utc 31 oct, 18 were frozen and **114 were missed** (deadlines 21:30 to 07:30), all scored as misses. the soak from 30 oct is void; it counts from 07:36 utc 31 oct, so the report is due after 07:36 utc 7 nov. g1's 30 clean days start 1 nov: 30 nov at the earliest. the challenger's window starts no earlier than 1 nov, so it closes no earlier than 30 dec; the 1 apr 2027 promotion date stands.
- **root cause:** as before: `sleep 1`, `autorestart 0`, agents not loaded after a reboot (why still not found). cause of the reboot not found.
- **fix:** agents reinstalled. **not fixed:** `sudo pmset -a sleep 0 autorestart 1` still needs the owner's password, and the next sleep or reboot stops the record again.
- **prevention:** unchanged: the pmset change, the login-items check, one deliberate reboot. this is the second miss, and the entry above says to move to an always-on host if the soak misses again; that's the owner's decision.
