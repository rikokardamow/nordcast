# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.28.1", "pyarrow>=21"]
# ///
"""Archive Energinet's real-time feeds before they age out.

Runs every minute from launchd (ops/launchd/nordcast.archive.plist). Each
source is pulled over a trailing window and appended to
<NORDCAST_ARCHIVE_REPO>/<source>/<yyyy-mm-dd>.parquet, one file per day of the data's
own time column. A row is stored once per distinct content, so re-running
adds nothing and a revised value is a new row with a later pulled_at_utc.
Pushes the archive repo once an hour.

A failing source is logged and skipped; the next minute's window covers it.
"""

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pyarrow as pa
import pyarrow.parquet as pq

EDS = "https://api.energidataservice.dk/dataset"
EMS = "https://electricitymarketservice.energinet.dk/api/v1/PublicData/dataset"
REPO = Path(os.environ.get("NORDCAST_ARCHIVE_REPO", Path.home() / "nordcast-archive"))
PUSH_EVERY = timedelta(hours=1)


def eds(dataset, offset, end_offset=None):
    params = {"start": "now", "startOffset": offset}
    if end_offset:
        params |= {"end": "now", "endOffset": end_offset}

    def fetch(client, now):
        r = client.get(f"{EDS}/{dataset}", params=params)
        r.raise_for_status()
        return r.json()["records"]

    return fetch


def mfrr_request(client, now):
    """One row per (issue time, MTU, area); the API nests areas."""
    since = (now - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = client.get(f"{EMS}/mfrrRequest/period", params={"from": since})
    r.raise_for_status()
    return [
        {"timeStamp": x["timeStamp"], "mtuStart": x["mtuStart"], **v}
        for x in r.json()["mfrrRequest"]
        for v in x["values"]
    ]


# name: (fetch, time column the daily partition is cut on, every n minutes)
# Energi Data Service limits per IP, so the slower feeds run every 5 minutes.
SOURCES = {
    "power_system_right_now": (eds("PowerSystemRightNow", "-PT30M"), "Minutes1UTC", 1),
    "prodex_5min": (eds("ElectricityProdex5MinRealtime", "-PT30M"), "Minutes5UTC", 1),
    "imbalance_price": (eds("ImbalancePrice", "-P2D"), "TimeUTC", 1),
    "mfrr_request": (mfrr_request, "mtuStart", 1),
    # its publication lag isn't measured yet; this measures it
    "mfrr_activation": (eds("MfrrEnergyActivationMarket", "-P1D"), "TimeUTC", 5),
    # the server overwrites each forecast; only the archive keeps the versions.
    # The next 2 h only: the calls look at most 61 min ahead, and the whole
    # horizon is reissued every 5 min (~580k rows a day uncapped).
    "forecasts_5min": (eds("Forecasts_5Min", "-PT30M", "PT2H"), "Minutes5UTC", 5),
}


def row_key(record):
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def append(repo, source, time_col, records, pulled_at):
    """Add records not already stored. Returns how many were new."""
    by_day = {}
    for rec in records:
        by_day.setdefault(rec[time_col][:10], []).append(rec)
    added = 0
    for day, recs in by_day.items():
        path = Path(repo) / source / f"{day}.parquet"
        old = pq.read_table(path) if path.exists() else None
        seen = set(old.column("row_key").to_pylist()) if old is not None else set()
        new, keys = [], set()
        for rec in recs:
            k = row_key(rec)
            if k not in seen and k not in keys:
                keys.add(k)
                new.append({"row_key": k, "pulled_at_utc": pulled_at, **rec})
        if not new:
            continue
        table = pa.Table.from_pylist(new)
        if old is not None:
            # a column Energinet adds or drops shows up as nulls, not a crash
            table = pa.concat_tables([old, table], promote_options="permissive")
        path.parent.mkdir(parents=True, exist_ok=True)
        # write then rename, so a reader never sees a half-written file
        tmp = path.with_suffix(".parquet.tmp")
        pq.write_table(table, tmp)
        os.replace(tmp, path)
        added += len(new)
    return added


def git(*args, check=True, **kw):
    return subprocess.run(["git", "-C", str(REPO), *args], check=check, **kw)


def push_if_due(now):
    last = git("log", "-1", "--format=%cI", capture_output=True, text=True, check=False)
    if (
        last.stdout.strip()
        and now - datetime.fromisoformat(last.stdout.strip()) < PUSH_EVERY
    ):
        return
    git("add", "-A")
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        return
    git("commit", "-q", "-m", f"Archive {now:%Y-%m-%d %H:%M} UTC")
    git("push", "-q", "-u", "origin", "HEAD")
    print("pushed")


def main():
    now = datetime.now(UTC)
    failed = False
    with httpx.Client(timeout=30) as client:
        for name, (fetch, time_col, every) in SOURCES.items():
            if now.minute % every:
                continue
            try:
                n = append(REPO, name, time_col, fetch(client, now), now)
                print(f"{now:%FT%TZ} {name}: +{n}")
            except Exception as exc:  # noqa: BLE001 - one source never stops the others
                failed = True
                print(f"{now:%FT%TZ} {name} failed: {type(exc).__name__}: {exc}"[:300])
    try:
        push_if_due(now)
    except subprocess.CalledProcessError as exc:
        print(f"{now:%FT%TZ} push failed: {exc}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
