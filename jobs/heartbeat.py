"""Write status/heartbeat.json every 5 min and print what is wrong.

Runs every minute from ops/run_jobs.sh and does nothing until the last one is
5 min old. Local only: no commit, no push.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from _common import ARCHIVE, DB_URL

from nordcast import heartbeat

PATH = Path("status/heartbeat.json")


def main(now=None):
    now = now or datetime.now(UTC)
    if not heartbeat.due(PATH, now):
        return None
    with psycopg.connect(DB_URL) as conn:
        beat = heartbeat.build(conn, now, ARCHIVE)
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(beat, indent=2) + "\n")
    for problem in heartbeat.problems(beat, now):
        print(f"ALARM {problem}")
    return beat


if __name__ == "__main__":
    main()
