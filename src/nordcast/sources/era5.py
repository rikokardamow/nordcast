"""ERA5 reanalysis: 100 m wind at the six DK1 points, from the Copernicus CDS.

Reanalysis is truth, not a forecast: it knows the weather it describes, so a
backtest using it looks better than live. It stays in series named era5.* and
is never a forecast or a live feature (notes/backfill.md).

Values are from the 0.25 degree grid cell nearest each point. Data CC BY 4.0;
the key is read by cdsapi from ~/.cdsapirc.
"""

import calendar
import math
from datetime import UTC, datetime

from nordcast.sources.open_meteo import POINTS

DATASET = "reanalysis-era5-single-levels"
LICENCE = "cc-by"
LICENCE_URL = f"https://cds.climate.copernicus.eu/datasets/{DATASET}?tab=download"
GRID = 0.25
VARIABLES = ["100m_u_component_of_wind", "100m_v_component_of_wind"]


def series_id(point):
    return f"era5.{point}.ws100"


def _on_grid(x):
    return round(x / GRID) * GRID


def area(points=POINTS):
    """[north, west, south, east]: the smallest box holding each nearest cell."""
    lats = [_on_grid(lat) for lat, _ in points.values()]
    lons = [_on_grid(lon) for _, lon in points.values()]
    return [max(lats), min(lons), min(lats), max(lons)]


def request(year, month, days=None):
    """The CDS request for a month, or for some of its days."""
    days = days or range(1, calendar.monthrange(year, month)[1] + 1)
    return {
        "product_type": ["reanalysis"],
        "variable": VARIABLES,
        "year": [f"{year}"],
        "month": [f"{month:02d}"],
        "day": [f"{d:02d}" for d in days],
        "time": [f"{h:02d}:00" for h in range(24)],
        "area": area(),
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def wind_speed(u, v):
    return math.hypot(u, v)


def nearest(values, x):
    return min(range(len(values)), key=lambda i: abs(values[i] - x))


def to_rows(times, lats, lons, u100, v100, points=POINTS):
    """One row per point and hour. u100, v100 are [time][lat][lon]; None is no row."""
    out = []
    for point, (lat, lon) in points.items():
        i, j = nearest(lats, lat), nearest(lons, lon)
        for t, hour in enumerate(times):
            u, v = u100[t][i][j], v100[t][i][j]
            if u is None or v is None:
                continue
            out.append({"series_id": series_id(point), "observed_for": hour,
                        "value": wind_speed(u, v), "u100": u, "v100": v})  # fmt: skip
    return out


def read_netcdf(path):
    """Rows from a downloaded file."""
    from netCDF4 import Dataset  # optional group "era5"

    with Dataset(path) as ds:
        times = [
            datetime.fromtimestamp(int(s), UTC) for s in ds["valid_time"][:].tolist()
        ]
        return to_rows(
            times,
            ds["latitude"][:].tolist(),
            ds["longitude"][:].tolist(),
            ds["u100"][:].tolist(),
            ds["v100"][:].tolist(),
        )
