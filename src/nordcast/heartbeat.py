"""The record's health check, local to this Mac.

jobs/heartbeat.py writes status/heartbeat.json every 5 min: when it was
written, the last headline freeze, the last 24 h's on-time freeze rate and the
newest pull of each archive feed. `problems` says what's wrong: a last freeze
more than 20 min old or a last mfrrRequest pull more than 15 min old when it
was written. ops/run_jobs.sh logs them and raises a Mac notification. Nothing
leaves the machine, so it can't report a Mac that is off or asleep.

By hand, which also fails on a file over 75 min old:
`python src/nordcast/heartbeat.py status/heartbeat.json`. Standard library only.
"""

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

MAX_AGE = timedelta(minutes=75)
# a freeze about every 15 min (every horizon's window opens at minutes 10-15
# of the quarter hour), plus the 5-min window, so a heartbeat written just
# before the next freeze doesn't raise a false alarm
MAX_FREEZE_AGE = timedelta(minutes=20)
MAX_PULL_AGE = timedelta(minutes=15)  # the archive pulls every 1-5 min
WATCHED_FEED = "mfrr_request"  # every minute, and gone after 7 days
EVERY = timedelta(minutes=5)
HORIZONS = (15, 30, 60)


def _iso(t):
    return None if t is None else t.astimezone(UTC).isoformat(timespec="seconds")


def _parse(s):
    return None if s is None else datetime.fromisoformat(s)


def on_time(conn, now, span=timedelta(hours=24)):
    """Calls due in the last `span` whose freeze window has passed, and how
    many have a headline row: the SLO in notes/controls.md. Counted from the
    record's first headline freeze, as scorecard.due_since does."""
    due, frozen = conn.execute(
        "select count(*), count(f.forecast_id) from release r"
        " cross join unnest(%s::int[]) as h(horizon)"
        " left join forecast f on f.release_id = r.release_id"
        "   and f.source_kind = 'model' and f.horizon_min = h.horizon"
        " where r.release_kind = 'dk1_isp'"
        " and r.period_end >= coalesce((select min(r0.period_end) from forecast f0"
        "   join release r0 using (release_id) where f0.source_kind = 'model'),"
        "   'infinity')"
        " and r.period_end - make_interval(mins => h.horizon) <= %s"
        " and r.period_end - make_interval(mins => h.horizon) > %s",
        (list(HORIZONS), now, now - span),
    ).fetchone()
    return {
        "due": due,
        "frozen": frozen,
        "rate": round(frozen / due, 4) if due else None,
    }


def archive_pulls(archive, now):
    """{feed: newest pulled_at_utc} over today's and yesterday's partitions."""
    import pyarrow.parquet as pq

    out = {}
    for folder in sorted(p for p in Path(archive).iterdir() if p.is_dir()):
        if folder.name.startswith("."):
            continue
        latest = None
        for day in (now - timedelta(days=1), now):
            path = folder / f"{day:%Y-%m-%d}.parquet"
            if path.exists():
                col = pq.read_table(path, columns=["pulled_at_utc"]).column(0)
                newest = max(col.to_pylist(), default=None)
                latest = max(filter(None, (latest, newest)), default=None)
        out[folder.name] = _iso(latest)
    return out


def build(conn, now, archive):
    last = conn.execute(
        "select max(frozen_at) from forecast where source_kind = 'model'"
    ).fetchone()[0]
    challenger = conn.execute(
        "select count(*) from forecast where source_kind = 'challenger'"
        " and frozen_at > %s",
        (now - timedelta(hours=24),),
    ).fetchone()[0]
    return {
        "generated_at": _iso(now),
        "last_freeze_at": _iso(last),
        "on_time_24h": on_time(conn, now),
        "challenger_rows_24h": challenger,
        "archive_last_pull": archive_pulls(archive, now),
    }


def due(path, now):
    """True when the heartbeat on disk is missing or older than EVERY."""
    path = Path(path)
    if not path.exists():
        return True
    return now - _parse(json.loads(path.read_text())["generated_at"]) >= EVERY


def problems(beat, now):
    """What is wrong; empty when the record is freezing and archiving."""
    out = []
    written = _parse(beat.get("generated_at"))
    if written is None or now - written > MAX_AGE:
        out.append(f"heartbeat written {beat.get('generated_at')}, over {MAX_AGE} ago")
    last = _parse(beat.get("last_freeze_at"))
    if last is None or (written and written - last > MAX_FREEZE_AGE):
        out.append(
            f"last freeze {beat.get('last_freeze_at')} was over {MAX_FREEZE_AGE}"
            f" old at {beat.get('generated_at')}"
        )
    pull = _parse(beat.get("archive_last_pull", {}).get(WATCHED_FEED))
    if pull is None or (written and written - pull > MAX_PULL_AGE):
        out.append(f"archive's last {WATCHED_FEED} pull {pull} was over {MAX_PULL_AGE}"
                   f" old at {beat.get('generated_at')}")  # fmt: skip
    return out


if __name__ == "__main__":
    beat = json.loads(Path(sys.argv[1]).read_text())
    found = problems(beat, datetime.now(UTC))
    print(json.dumps(beat, indent=2))
    for p in found:
        print(f"problem: {p}")
    sys.exit(1 if found else 0)
