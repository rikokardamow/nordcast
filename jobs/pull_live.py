"""Load what the archive pulled since the last run into the record."""

from datetime import UTC, datetime

import psycopg
from _common import ARCHIVE, DB_URL

from nordcast import live
from nordcast.runlog import logged

STATE = "data/live_state.json"

with (
    logged(lambda: psycopg.connect(DB_URL), "pull_live") as run,
    psycopg.connect(DB_URL) as conn,
):
    added = live.load(conn, ARCHIVE, datetime.now(UTC), STATE)
    run.detail = " ".join(f"{k}+{v}" for k, v in added.items())
    if not any(added.values()):
        run.nothing_due(run.detail)
    print(f"pull_live: {run.detail}")
