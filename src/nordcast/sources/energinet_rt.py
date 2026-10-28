"""Energinet's real-time market API: mfrrRequest, DK1.

https://electricitymarketservice.energinet.dk/api/v1/PublicData, no key,
at most 1 request a second. The request for an MTU is reissued every minute
from 7.5 minutes before it starts; each issue is a vintage, published at its
own timeStamp, so these rows are exact, not estimated. Only 7 days are kept:
anything older comes from the archive (jobs/archive.py).
"""

from datetime import UTC, datetime

import httpx

BASE_URL = "https://electricitymarketservice.energinet.dk/api/v1/PublicData/dataset"
SERIES_ID = "energinet.dk1.mfrr_request"


def fetch(start, end=None, client=None):
    params = {"from": start.strftime("%Y-%m-%dT%H:%M:%SZ")}
    if end is not None:
        params["to"] = end.strftime("%Y-%m-%dT%H:%M:%SZ")
    own = client is None
    client = client or httpx.Client(timeout=60)
    try:
        r = client.get(f"{BASE_URL}/mfrrRequest/period", params=params)
        r.raise_for_status()
        return r.json()["mfrrRequest"]
    finally:
        if own:
            client.close()


def _utc(s):
    return datetime.fromisoformat(s).astimezone(UTC)


def to_observations(issues):
    """Flat rows {timeStamp, mtuStart, area, value} or the API's nested ones."""
    flat = []
    for x in issues:
        if "values" in x:
            flat += [
                {"timeStamp": x["timeStamp"], "mtuStart": x["mtuStart"], **v}
                for v in x["values"]
            ]
        else:
            flat.append(x)
    return [
        {
            "series_id": SERIES_ID,
            "observed_for": _utc(r["mtuStart"]),
            "value": r["value"],
            "published_at": _utc(r["timeStamp"]),
            "vintage_quality": "exact",
        }
        for r in flat
        if r["area"] == "DK1" and r["value"] is not None
    ]
