"""The public proof: one file per Copenhagen day with every call frozen that day.

Runs from ops/run_jobs.sh after 00:10 Copenhagen, and is safe any time:
- a finished day with frozen rows and no file gets forecasts/frozen/dk1-<day>.json
  (the rows in freeze order, each with its sha256), a .sha256 of the file and
  an OpenTimestamps .ots, committed together; a day already written is never
  rewritten;
- a pending .ots is upgraded once its Bitcoin block exists.
The file proves the rows existed by the time it was stamped, after the day's
ISPs; the per-row hashes and the database trigger cover the time before.
Changed files are committed; ops/run_jobs.sh pushes them.
"""

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
from _common import DB_URL

from nordcast import stamp
from nordcast.calendar import COPENHAGEN, today_copenhagen
from nordcast.runlog import logged

FROZEN = Path("forecasts/frozen")


def day_rows(conn, day):
    start = datetime(day.year, day.month, day.day, tzinfo=COPENHAGEN)
    end = start + timedelta(days=1)
    rows = conn.execute(
        "select payload from forecast where frozen_at >= %s and frozen_at < %s"
        " order by frozen_at, forecast_id",
        (start.astimezone(UTC), end.astimezone(UTC)),
    ).fetchall()
    return [r[0] for r in rows]


def unstamped_days(conn, today):
    days = conn.execute(
        "select distinct (frozen_at at time zone 'Europe/Copenhagen')::date"
        " from forecast order by 1"
    ).fetchall()
    return [d for (d,) in days if d < today and not (FROZEN / f"dk1-{d}.json").exists()]


def write_day(conn, day):
    path = FROZEN / f"dk1-{day}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(day_rows(conn, day), indent=1, sort_keys=True) + "\n")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    Path(f"{path}.sha256").write_text(f"{digest}  {path.name}\n")
    files = [path, Path(f"{path}.sha256")]
    if proof := stamp.stamp(path):
        files.append(proof)
    return files


def main(now=None):
    now = now or datetime.now(UTC)
    changed = []
    with (
        logged(lambda: psycopg.connect(DB_URL), "stamp_daily") as run,
        psycopg.connect(DB_URL) as conn,
    ):
        for day in unstamped_days(conn, today_copenhagen(now)):
            changed += write_day(conn, day)
        for proof in sorted(FROZEN.glob("dk1-*.json.ots")):
            if not stamp.is_complete(proof) and stamp.upgrade(proof):
                changed.append(proof)
        run.detail = ", ".join(p.name for p in changed) or None
        if not changed:
            run.nothing_due()
            return []
    files = [str(p) for p in changed]
    subprocess.run(["git", "add", *files], check=True)
    msg = f"Stamp {', '.join(sorted({p.name.split('.')[0] for p in changed}))}"
    subprocess.run(["git", "commit", "-q", "-m", msg, "--", *files], check=True)
    print(msg)
    return changed


if __name__ == "__main__":
    sys.exit(0 if main() is not None else 1)
