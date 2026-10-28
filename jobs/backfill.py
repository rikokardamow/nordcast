"""Load history from each dataset's inception as estimated vintages.

    uv run python jobs/backfill.py            # probe, pull, load
    uv run python jobs/backfill.py --probe    # only write notes/inception.md

Raw rows are cached per month in data/history/<dataset>/<yyyy-mm>.parquet
(gitignored, rebuilt by re-running). Finished months are never refetched;
the current month always is. Loading is idempotent: the observation trigger
skips a row that repeats the newest vintage, so a re-run adds 0 rows.

Long 5-min and forecast datasets (from 2015 and 2019) start at FLOOR: the
model trains from 1 Oct 2025 and the oldest regime that matters starts
4 Mar 2025. Pass --from to go further back.
"""

import argparse
import json
import os
import time
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import psycopg
import pyarrow as pa
import pyarrow.parquet as pq

from nordcast import store
from nordcast.runlog import logged
from nordcast.sources import energinet, esett

LOCAL_DB = "postgresql://postgres:postgres@127.0.0.1:44332/postgres"
HISTORY = Path("data/history")
FLOOR = date(2025, 3, 1)
ESETT_INCEPTION = date(2021, 11, 1)
PAUSE = 2  # seconds between Energi Data Service calls; the archive shares the limit


def inception(dataset):
    url = f"https://api.energidataservice.dk/meta/dataset/{dataset}"
    meta = httpx.get(url, timeout=30).raise_for_status().json()
    return datetime.fromisoformat(meta["dataFrom"]).date()


def months(first, last):
    d = date(first.year, first.month, 1)
    while d <= last:
        nxt = date(d.year + d.month // 12, d.month % 12 + 1, 1)
        yield d, nxt
        d = nxt


def cached(dataset, month, nxt, today, pull):
    path = HISTORY / dataset / f"{month:%Y-%m}.parquet"
    if path.exists() and nxt <= today:
        return pq.read_table(path).to_pylist()
    rows = pull()
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows or [{"_empty": True}]), path)
    return rows


def _utc(d):
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


def write_inception(starts, today, path=Path("notes/inception.md")):
    lines = [
        "# inception – first row per dataset",
        "",
        (
            f"probed {today:%-d %b %Y} by jobs/backfill.py (energi data service"
            " `dataFrom`; esett from its documented start, checked by the first pull)."
        ),
        "",
        "| dataset | inception | backfilled from |",
        "|---|---|---|",
    ]
    lines += [f"| {d} | {i} | {f} |" for d, (i, f) in sorted(starts.items())]
    path.write_text("\n".join(lines) + "\n")


def backfill(conn, today, floor=FLOOR):
    starts, counts = {}, {}
    for dataset in energinet.DATASETS:
        first = inception(dataset)
        start = max(first, floor)
        starts[dataset] = (first, start)
        for month, nxt in months(start, today):
            rows = cached(
                dataset, month, nxt, today,
                lambda m=month, n=nxt, d=dataset: (
                    time.sleep(PAUSE) or energinet.fetch(d, _utc(m), _utc(n))
                ),
            )  # fmt: skip
            rows = [r for r in rows if "_empty" not in r]
            obs = energinet.to_observations(dataset, rows)
            added = store.insert_observations(conn, obs)
            conn.commit()
            counts[dataset] = counts.get(dataset, 0) + added
            print(f"{dataset} {month:%Y-%m}: {len(rows)} rows, +{added} observations")
    starts["eSett EXP14 (dk1)"] = (ESETT_INCEPTION, ESETT_INCEPTION)
    for month, nxt in months(ESETT_INCEPTION, today):
        rows = cached(
            "esett_exp14", month, nxt, today,
            lambda m=month, n=nxt: esett.fetch(_utc(m), _utc(n)),
        )  # fmt: skip
        rows = [r for r in rows if "_empty" not in r]
        added = store.insert_observations(conn, esett.to_observations(rows))
        conn.commit()
        counts["esett"] = counts.get("esett", 0) + added
        print(f"esett {month:%Y-%m}: {len(rows)} rows, +{added} observations")
    return starts, counts


def series_counts(conn):
    return conn.execute(
        "select series_id, count(*), min(observed_for), max(observed_for)"
        " from observation group by series_id order by series_id"
    ).fetchall()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--from", dest="floor", type=date.fromisoformat, default=FLOOR)
    args = ap.parse_args()
    today = datetime.now(UTC).date()
    if args.probe:
        write_inception(
            {
                d: (inception(d), max(inception(d), args.floor))
                for d in energinet.DATASETS
            },
            today,
        )
        return
    url = os.environ.get("NORDCAST_DATABASE_URL", LOCAL_DB)
    with (
        logged(lambda: psycopg.connect(url), "backfill") as run,
        psycopg.connect(url) as conn,
    ):
        starts, counts = backfill(conn, today, args.floor)
        write_inception(starts, today)
        run.detail = json.dumps(counts)
        for row in series_counts(conn):
            print(*row, sep=" | ")


if __name__ == "__main__":
    main()
