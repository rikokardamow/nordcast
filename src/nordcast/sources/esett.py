"""eSett open data: DK1 imbalance price and direction, the cross-check source.

- No key. EXP14/Prices, 15 min, DK1 from 1 Nov 2021 (quarters within an
  hour are identical until 19 Mar 2025).
- An ISP not yet published comes back with 0.0 in every column, which looks
  like a real price. Such rows are dropped, never loaded as zeros.
- First print ~1 h after the ISP (research note, 28 Oct 2026); the nominal
  lag errs late at 2 h.
"""

import time
from datetime import UTC, datetime, timedelta

import httpx

BASE_URL = "https://api.opendata.esett.com/EXP14/Prices"
DK1 = "10YDK-1--------W"
ISP = timedelta(minutes=15)
PRICE_COLS = ("imblSalesPrice", "imblPurchasePrice", "upRegPrice", "downRegPrice")
RETRIES = 5


def _after_end(minutes):
    return lambda isp: isp + ISP + timedelta(minutes=minutes)


SERIES = {
    "esett.dk1.imbalance_price_eur": ("imblSalesPrice", _after_end(120)),
    "esett.dk1.direction": ("mainDirRegPowerPerMBA", _after_end(120)),
}
NOMINAL_LAG = {sid: lag for sid, (_, lag) in SERIES.items()}


class ESettError(Exception):
    pass


def fetch(start, end, client=None, sleep=time.sleep):
    params = {
        "start": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "end": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "mba": DK1,
    }
    own = client is None
    client = client or httpx.Client(timeout=120)
    try:
        for attempt in range(RETRIES):
            try:
                r = client.get(BASE_URL, params=params)
            except httpx.TransportError:
                sleep(2**attempt)
                continue
            if r.status_code == 429 or r.status_code >= 500:
                sleep(60 if r.status_code == 429 else 2**attempt)
                continue
            r.raise_for_status()
            return r.json()
        raise ESettError(f"EXP14 {start:%F}..{end:%F}: gave up after {RETRIES} tries")
    finally:
        if own:
            client.close()


def published(row):
    return any(row.get(c) not in (0, 0.0, None) for c in PRICE_COLS)


def to_observations(records):
    out = []
    for row in records:
        if not published(row):
            continue
        isp = datetime.fromisoformat(row["timestampUTC"]).astimezone(UTC)
        for series_id, (col, lag) in SERIES.items():
            if row.get(col) is None:
                continue
            out.append(
                {
                    "series_id": series_id,
                    "observed_for": isp,
                    "value": row[col],
                    "published_at": lag(isp),
                    "vintage_quality": "estimated",
                }
            )
    return out
