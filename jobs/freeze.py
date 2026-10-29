"""Freeze every call due now: each ISP 15, 30 and 60 min ahead.

Extends the release calendar to the end of tomorrow first, so it never runs
out. A failure on one ISP is logged and the others still freeze. LightGBM v1
is frozen beside them as a challenger; its misses go in the run's detail
and never fail the job.
"""

from datetime import UTC, datetime, timedelta

import psycopg
from _common import DB_URL

from nordcast import challenger, freeze, schedule, store
from nordcast.calendar import RELEASE_KIND, isp_releases, today_copenhagen
from nordcast.runlog import logged

now = datetime.now(UTC)
missed = []
try:
    challengers = [(challenger.METHOD, challenger.lightgbm(challenger.load()))]
except Exception as exc:  # noqa: BLE001 - the headline freezes without it
    challengers = []
    missed.append(f"{challenger.METHOD} not loaded: {type(exc).__name__}: {exc}"[:200])
with (
    logged(lambda: psycopg.connect(DB_URL), "freeze") as run,
    psycopg.connect(DB_URL) as conn,
):
    today = today_copenhagen(now)
    store.load_releases(
        conn, "energinet", RELEASE_KIND, isp_releases(today, today + timedelta(days=1))
    )
    conn.commit()
    frozen, failed = [], []
    for h in freeze.HORIZONS:
        for release in schedule.due_for_freeze(conn, now, h):
            try:
                freeze.freeze_rows(conn, release, h, now, challengers=challengers,
                                   missed=missed)  # fmt: skip
                conn.commit()  # each ISP stands alone
                frozen.append(f"{release[1]:%H:%M}/h{h}")
            except Exception as exc:  # noqa: BLE001 - one ISP never blocks the next
                conn.rollback()
                failed.append(
                    f"{release[1]:%H:%M}/h{h} {type(exc).__name__}: {exc}"[:200]
                )
    run.detail = (
        f"frozen {frozen}"
        + (f" failed {failed}" if failed else "")
        + (f" challenger missed {missed}" if missed and frozen else "")
    )
    print(f"freeze: {run.detail}")
    if failed:
        raise RuntimeError(f"{len(failed)} freezes failed: {failed}")
    if not frozen:
        run.nothing_due()
