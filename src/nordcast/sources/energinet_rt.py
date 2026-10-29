"""Energinet's real-time market API: mfrrRequest, DK1.

https://electricitymarketservice.energinet.dk/api/v1/PublicData, no key,
at most 1 request a second. The request for an MTU is reissued every minute.
Each issue is a vintage, but its `timeStamp` is when it was *issued to the
AOF*, which can be 20+ minutes before Energinet *publishes* it: "for a given
MTU the values are not published until 7.5 minutes before start of the MTU"
(API guide). So a row is published at its pull time when the archive saw it
(exact), and otherwise no earlier than mtuStart - 7.5 min. Using timeStamp, as
the first version did, leaked an MTU's request ~15 minutes early; those rows
are kept under the superseded `energinet.dk1.mfrr_request` (29 Oct 2026).
Only 7 days are kept upstream: anything older comes from the archive.
"""

from datetime import UTC, datetime, timedelta

import httpx

BASE_URL = "https://electricitymarketservice.energinet.dk/api/v1/PublicData/dataset"
SERIES_ID = "energinet.dk1.mfrr_request_public"
PUBLISHED_BEFORE_START = timedelta(minutes=7, seconds=30)


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
            "published_at": published(r),
            "vintage_quality": "exact",
        }
        for r in flat
        if r["area"] == "DK1" and r["value"] is not None
    ]


def published(row):
    """When a request became public: the archive's pull time if it has one, else
    the later of its issue time and the MTU start less 7.5 minutes."""
    pulled = row.get("pulled_at_utc")
    if pulled is not None:
        return pulled if isinstance(pulled, datetime) else _utc(pulled)
    return max(_utc(row["timeStamp"]), _utc(row["mtuStart"]) - PUBLISHED_BEFORE_START)
