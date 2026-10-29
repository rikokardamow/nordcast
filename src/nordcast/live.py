"""Load the archive's new rows into the record as exact vintages.

The archive (jobs/archive.py) pulls Energinet every minute and keeps every
version of every row with its pulled_at_utc. This replays those pulls in
order: after each pull, the ISPs it touched are rebuilt from the newest
version of each row and loaded with published_at = that pull's time and
vintage_quality 'exact'. The observation trigger skips a value that repeats
the newest vintage, so replaying a pull twice adds nothing.

Reading the archive instead of calling the APIs again keeps one client per
rate limit.
"""

import json
from datetime import timedelta
from pathlib import Path

import pyarrow.parquet as pq

from nordcast import store
from nordcast.sources import energinet, energinet_rt

# archive folder -> Energi Data Service dataset
DATASETS = {
    "imbalance_price": "ImbalancePrice",
    "mfrr_activation": "MfrrEnergyActivationMarket",
    "prodex_5min": "ElectricityProdex5MinRealtime",
    "forecasts_5min": "Forecasts_5Min",
    "day_ahead_prices": "DayAheadPrices",
}
KEY_EXTRA = ("PriceArea", "ForecastType")


def _partitions(archive, folder, now):
    days = [(now + timedelta(days=d)).date() for d in (-2, -1, 0, 1)]
    paths = [Path(archive) / folder / f"{d}.parquet" for d in days]
    rows = []
    for p in paths:
        if p.exists():
            rows += pq.read_table(p).to_pylist()
    return rows


def _isp(t):
    return t - timedelta(minutes=t.minute % 15, seconds=t.second)


def replay(dataset, rows, since):
    """Exact observations for every pull after `since`, in pull order."""
    specs = {sid: s for sid, s in energinet.SERIES.items() if s.dataset == dataset}
    time_col = next(iter(specs.values())).time_col
    rows = sorted(
        (r for r in rows if r.get("PriceArea") == "DK1"),
        key=lambda r: r["pulled_at_utc"],
    )
    latest, out, i = {}, [], 0
    while i < len(rows):
        pulled = rows[i]["pulled_at_utc"]
        touched = set()
        while i < len(rows) and rows[i]["pulled_at_utc"] == pulled:
            r = rows[i]
            latest[(r[time_col], *(r.get(k) for k in KEY_EXTRA))] = r
            touched.add(_isp(energinet._utc(r[time_col])))
            i += 1
        if since is not None and pulled <= since:
            continue
        current = [
            r for r in latest.values() if _isp(energinet._utc(r[time_col])) in touched
        ]
        for sid, spec in specs.items():
            for isp, value in energinet.isp_values(spec, current).items():
                out.append(
                    {
                        "series_id": sid,
                        "observed_for": isp,
                        "value": round(value, 4),
                        "published_at": pulled,
                        "vintage_quality": "exact",
                    }
                )
    return out


def load(conn, archive, now, state_path):
    """Load everything pulled since the last run. Returns {folder: rows added}."""
    state_path = Path(state_path)
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    added = {}
    for folder, dataset in DATASETS.items():
        rows = _partitions(archive, folder, now)
        if not rows:
            continue
        since = state.get(folder)
        since = (
            None
            if since is None
            else type(rows[0]["pulled_at_utc"]).fromisoformat(since)
        )
        added[folder] = store.insert_observations(conn, replay(dataset, rows, since))
        state[folder] = max(r["pulled_at_utc"] for r in rows).isoformat()
    # each row carries its own issue time, so only the watermark is needed here
    rows = _partitions(archive, "mfrr_request", now)
    if rows:
        since = state.get("mfrr_request")
        new = [
            r for r in rows if since is None or r["pulled_at_utc"].isoformat() > since
        ]
        added["mfrr_request"] = store.insert_observations(
            conn, energinet_rt.to_observations(new)
        )
        state["mfrr_request"] = max(r["pulled_at_utc"] for r in rows).isoformat()
    conn.commit()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    return added
