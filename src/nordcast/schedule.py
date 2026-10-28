"""Which ISPs a job should act on right now.

launchd only wakes the jobs every minute. The release table decides what
they do, so clock changes need no edits.
"""

from datetime import timedelta

WINDOW = timedelta(minutes=5)


def due_for_freeze(conn, now, horizon):
    """ISPs starting h to h+5 min from now with no model call for that horizon.

    A call frozen in this window is at least h minutes ahead: on time by
    construction. An ISP whose window passed without a freeze is a miss and
    is never frozen late at a shorter horizon."""
    h = timedelta(minutes=horizon)
    return conn.execute(
        "select r.release_id, r.period_end, r.scheduled_at from release r"
        " where r.release_kind = 'dk1_isp'"
        " and r.period_end >= %s and r.period_end <= %s"
        " and not exists (select 1 from forecast f where f.release_id = r.release_id"
        "   and f.source_kind = 'model' and f.horizon_min = %s)"
        " order by r.period_end",
        (now + h, now + h + WINDOW, horizon),
    ).fetchall()


def due_for_score(conn, now):
    """ISPs with a frozen call not scored yet, from the last 14 days."""
    rows = conn.execute(
        "select distinct r.period_end from release r"
        " join forecast f on f.release_id = r.release_id"
        " left join score s on s.forecast_id = f.forecast_id"
        " where r.release_kind = 'dk1_isp' and r.period_end < %s"
        " and r.period_end > %s - interval '14 days' and s.score_id is null"
        " order by r.period_end",
        (now, now),
    ).fetchall()
    return [r[0] for r in rows]
