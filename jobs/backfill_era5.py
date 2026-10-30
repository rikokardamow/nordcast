"""Load ERA5 100 m wind at the six points into parquet, one month per request.

    uv run --group era5 python jobs/backfill_era5.py --dry-run
    uv run --group era5 python jobs/backfill_era5.py --from 2025-03-01

Cached in data/history/era5/<yyyy-mm>.parquet and raw/<yyyy-mm>.nc (gitignored);
finished months are never refetched, so a re-run sends nothing. Parquet only:
nothing goes into postgres, and no model or live job reads these series.

CDS may disable accounts over parallel or repeated invalid requests (announcement
of 22 Oct 2026), so requests run one at a time and any error stops the run; there
are no retries. Preliminary ERA5T data is replaced after two to three months, so
by default a month is fetched only once it ended SETTLED ago.
"""

import argparse
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from nordcast.sources import era5

HISTORY = Path("data/history/era5")
FLOOR = date(2025, 3, 1)
SETTLED = timedelta(days=90)


def months(first, last):
    """(year, month) of each month from first's that has ended by last."""
    y, m = first.year, first.month
    while (date(y + m // 12, m % 12 + 1, 1)) <= last:
        yield y, m
        y, m = y + m // 12, m % 12 + 1


def missing(first, last, history=HISTORY):
    return [
        (y, m)
        for y, m in months(first, last)
        if not (history / f"{y}-{m:02d}.parquet").exists()
    ]


def licence_accepted(accepted):
    return any(a["id"] == era5.LICENCE for a in accepted)


def backfill(todo, retrieve, read=era5.read_netcdf, history=HISTORY):
    """Fetch months in order, one at a time. An error propagates and stops the run."""
    (history / "raw").mkdir(parents=True, exist_ok=True)
    total = 0
    for y, m in todo:
        raw = history / "raw" / f"{y}-{m:02d}.nc"
        if not raw.exists():
            part = raw.with_suffix(".part")
            retrieve(era5.DATASET, era5.request(y, m), str(part))
            part.rename(raw)
        rows = read(raw)
        path = history / f"{y}-{m:02d}.parquet"
        part = path.with_suffix(".part")
        pq.write_table(pa.Table.from_pylist(rows), part)
        part.rename(path)
        total += len(rows)
        print(f"{y}-{m:02d}: {len(rows)} rows", flush=True)
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="first", type=date.fromisoformat, default=FLOOR)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    todo = missing(args.first, datetime.now(UTC).date() - SETTLED)
    print(f"{len(todo)} months to fetch")
    if args.dry_run or not todo:
        return

    import cdsapi
    from ecmwf.datastores import Client

    client = cdsapi.Client()
    accepted = Client(url=client.url, key=client.key).get_accepted_licences()
    if not licence_accepted(accepted):
        raise SystemExit(f"accept the ERA5 licence first: {era5.LICENCE_URL}")
    print(f"backfill_era5: +{backfill(todo, client.retrieve)} rows")


if __name__ == "__main__":
    main()
