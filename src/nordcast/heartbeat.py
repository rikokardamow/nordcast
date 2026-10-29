"""The Mac's heartbeat and the deadman that reads it.

jobs/heartbeat.py writes status/heartbeat.json and pushes it about hourly:
when it was written, the last headline freeze, the last 24 h's on-time
freeze rate and the newest pull of each archive feed. GitHub runs
`python src/nordcast/heartbeat.py status/heartbeat.json`
(.github/workflows/deadman.yml) on its own clock and fails, which emails
me, when the Mac has gone quiet: no push for 75 min, or a heartbeat whose
last freeze or last mfrrRequest pull was more than 15 min old when it was
written.

Standard library only, so the deadman needs no install.
"""

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

MAX_AGE = timedelta(minutes=75)
MAX_FREEZE_AGE = timedelta(minutes=15)  # an ISP every 15 min, three horizons
MAX_PULL_AGE = timedelta(minutes=15)  # the archive pulls every 1-5 min
WATCHED_FEED = "mfrr_request"  # every minute, and gone after 7 days
PUSH_EVERY = timedelta(minutes=55)
HORIZONS = (15, 30, 60)


def _iso(t):
    return None if t is None else t.astimezone(UTC).isoformat(timespec="seconds")


def _parse(s):
    return None if s is None else datetime.fromisoformat(s)


def on_time(conn, now, span=timedelta(hours=24)):
    """Calls due in the last `span` whose freeze window has passed, and how
    many have a headline row: the SLO in notes/controls.md."""
    due, frozen = conn.execute(
        "select count(*), count(f.forecast_id) from release r"
        " cross join unnest(%s::int[]) as h(horizon)"
        " left join forecast f on f.release_id = r.release_id"
        "   and f.source_kind = 'model' and f.horizon_min = h.horizon"
        " where r.release_kind = 'dk1_isp'"
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
    """True when the heartbeat on disk is missing or older than PUSH_EVERY."""
    path = Path(path)
    if not path.exists():
        return True
    return now - _parse(json.loads(path.read_text())["generated_at"]) >= PUSH_EVERY


def problems(beat, now):
    """What the deadman fails on; empty when the Mac is alive and freezing."""
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
        print(f"::error::{p}")
    sys.exit(1 if found else 0)
