"""Write status/heartbeat.json and commit it, about hourly.

Runs every minute from ops/run_jobs.sh and does nothing until the committed
heartbeat is 55 min old, so a skipped minute never opens a gap the deadman
(.github/workflows/deadman.yml, 75 min) would see. ops/run_jobs.sh pushes.
"""

import json
import subprocess
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
    subprocess.run(["git", "add", str(PATH)], check=True)
    msg = f"Heartbeat {now:%Y-%m-%d %H:%M} UTC"
    subprocess.run(["git", "commit", "-q", "-m", msg, "--", str(PATH)], check=True)
    print(msg)
    return beat


if __name__ == "__main__":
    main()
