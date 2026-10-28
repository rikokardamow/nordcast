"""Build the training rows for every horizon: data/training/h<h>.parquet.

    uv run --group models python jobs/build_training.py

Every target ISP from 1 Oct 2025 to a day ago, features as of its freeze
time, labels from the first print. Reads the record once into memory.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
from _common import DB_URL

from nordcast import features, freeze, model
from nordcast.calendar import isps

OUT = Path("data/training")

now = datetime.now(UTC)
with psycopg.connect(DB_URL) as conn:
    pit = features.load(conn, model.WINDOW_START - timedelta(days=35), now)
day, last = model.WINDOW_START.date(), (now - timedelta(days=1)).date()
targets = []
while day <= last:
    targets += isps(day)
    day += timedelta(days=1)
targets = [t for t in targets if t >= model.WINDOW_START]
OUT.mkdir(parents=True, exist_ok=True)
for h in freeze.HORIZONS:
    df = model.build_rows(pit, targets, h)
    df.to_parquet(OUT / f"h{h}.parquet")
    print(
        f"h{h}: {len(df)} rows of {len(targets)} ISPs, {df.target.min()} .. {df.target.max()}"
    )
