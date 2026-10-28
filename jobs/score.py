"""Score every frozen call whose ISP has a first print."""

from datetime import UTC, datetime

import psycopg
from _common import DB_URL

from nordcast import schedule, score
from nordcast.runlog import logged

now = datetime.now(UTC)
with (
    logged(lambda: psycopg.connect(DB_URL), "score") as run,
    psycopg.connect(DB_URL) as conn,
):
    written = 0
    for isp in schedule.due_for_score(conn, now):
        _, n = score.score_isp(conn, isp, now)
        written += n
    conn.commit()
    run.detail = f"{written} scores"
    if not written:
        run.nothing_due(run.detail)
    print(f"score: {run.detail}")
