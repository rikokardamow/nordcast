"""Load HARMONIE day-earlier wind history at the six points as estimated vintages.

    uv run python jobs/backfill_weather.py

Quarter by quarter from 29 Jun 2024 to today, cached in
data/history/open_meteo/<yyyy-qN>.json (gitignored); finished quarters are
never refetched. Idempotent: the observation trigger skips a repeat.
"""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import psycopg
from _common import DB_URL

from nordcast import store
from nordcast.runlog import logged
from nordcast.sources import open_meteo

CACHE = Path("data/history/open_meteo")


def quarters(first, last):
    d = first
    while d <= last:
        q_end = date(d.year + (d.month > 9), (((d.month - 1) // 3 + 1) * 3) % 12 + 1, 1)
        yield d, min(q_end - timedelta(days=1), last)
        d = q_end


today = datetime.now(UTC).date()
CACHE.mkdir(parents=True, exist_ok=True)
added = 0
with (
    logged(lambda: psycopg.connect(DB_URL), "backfill_weather") as run,
    psycopg.connect(DB_URL) as conn,
):
    for start, end in quarters(open_meteo.FIRST_DAY, today):
        path = CACHE / f"{start.year}-q{(start.month - 1) // 3 + 1}.json"
        if path.exists() and end < today:
            body = json.loads(path.read_text())
        else:
            body = open_meteo.fetch(start, end)
            path.write_text(json.dumps(body))
        n = store.insert_observations(conn, open_meteo.to_observations(body))
        conn.commit()
        added += n
        print(f"{start}..{end}: +{n}")
    run.detail = f"+{added}"
print(f"backfill_weather: +{added} observations")
