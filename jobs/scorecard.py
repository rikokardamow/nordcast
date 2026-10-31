"""Refresh the readme's scorecard from the scored record and commit it.

Runs from ops/run_jobs.sh after the daily stamp; ops/run_jobs.sh pushes.
Prints "Scorecard" when the readme changed.
"""

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from _common import DB_URL

from nordcast import scorecard

README = Path("README.md")

now = datetime.now(UTC)
with psycopg.connect(DB_URL) as conn:
    rows = conn.execute(scorecard.QUERY).fetchall()
    table = scorecard.lines(rows, scorecard.due_since(conn, now))
old = README.read_text()
new = scorecard.replace(old, scorecard.readme_block(table))
if new != old:
    README.write_text(new)
    msg = f"Scorecard {now:%Y-%m-%d}"
    subprocess.run(["git", "commit", "-q", "-m", msg, "--", str(README)], check=True)
    print(msg)
