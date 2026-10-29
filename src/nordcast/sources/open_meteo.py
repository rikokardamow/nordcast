"""Open-Meteo previous-runs API: DMI HARMONIE wind at six DK1 points, history.

The live archive (jobs/archive.py) records each forecast version as it is
pulled. This module loads the history before that: `previous_day1`, the
forecast for hour T from the HARMONIE run about a day earlier, from
29 Jun 2024 12:00 (the first hour the API has).

That run starts at least 24 h before T and is out a few hours later, so a
backfilled value is published at T - PUBLISHED_BEFORE (21 h): the late side,
so history never shows a forecast earlier than it existed. Estimated vintages.

Licence: data CC BY 4.0, "Weather data by Open-Meteo.com"; the free API is for
non-commercial use (notes/sources.md).
"""

import time
from datetime import UTC, date, datetime, timedelta

import httpx

URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
MODEL = "dmi_harmonie_arome_europe"
FIRST_DAY = date(2024, 6, 29)
PUBLISHED_BEFORE = timedelta(hours=21)
# Same six points as jobs/archive.py (a standalone script); a test keeps them equal.
POINTS = {
    "horns_rev": (55.48, 7.87),
    "anholt": (56.60, 11.20),
    "romo": (55.15, 8.50),
    "hvide_sande": (56.00, 8.12),
    "hanstholm": (57.12, 8.60),
    "skagen": (57.72, 10.59),
}
VARIABLES = {
    "ws100": "wind_speed_100m_previous_day1",
    "wd100": "wind_direction_100m_previous_day1",
}
RETRIES = 5


def series_id(point, var):
    return f"openmeteo.{point}.{var}_d1"


def fetch(start, end, client=None, sleep=time.sleep):
    """Hourly day-earlier forecasts at every point, [start, end] inclusive (dates)."""
    names = list(POINTS)
    params = {
        "latitude": ",".join(str(POINTS[n][0]) for n in names),
        "longitude": ",".join(str(POINTS[n][1]) for n in names),
        "hourly": ",".join(VARIABLES.values()),
        "models": MODEL,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "wind_speed_unit": "ms",
        "timezone": "UTC",
    }
    own = client is None
    client = client or httpx.Client(timeout=120)
    try:
        for attempt in range(RETRIES):
            r = client.get(URL, params=params)
            if r.status_code == 429 or r.status_code >= 500:
                sleep(60 if r.status_code == 429 else 2**attempt)
                continue
            r.raise_for_status()
            body = r.json()
            return dict(
                zip(names, body if isinstance(body, list) else [body], strict=True)
            )
        raise RuntimeError(f"open-meteo {start}..{end}: gave up after {RETRIES} tries")
    finally:
        if own:
            client.close()


def to_observations(by_point):
    """Estimated-vintage observation rows; a missing value is no row, never 0."""
    out = []
    for point, loc in by_point.items():
        hourly = loc["hourly"]
        for var, column in VARIABLES.items():
            for t, v in zip(hourly["time"], hourly[column], strict=True):
                if v is None:
                    continue
                hour = datetime.fromisoformat(t).replace(tzinfo=UTC)
                out.append({"series_id": series_id(point, var), "observed_for": hour,
                            "value": v, "published_at": hour - PUBLISHED_BEFORE,
                            "vintage_quality": "estimated"})  # fmt: skip
    return out
