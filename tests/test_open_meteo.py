import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

from nordcast.sources import open_meteo


def test_the_points_match_the_archive():
    spec = importlib.util.spec_from_file_location(
        "archive", Path(__file__).parent.parent / "jobs" / "archive.py"
    )
    archive = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(archive)
    assert archive.WEATHER_POINTS == open_meteo.POINTS


def test_a_day_earlier_forecast_is_published_21_hours_before_its_hour():
    body = {"horns_rev": {"hourly": {
        "time": ["2026-10-01T12:00", "2026-10-01T13:00"],
        "wind_speed_100m_previous_day1": [9.5, None],
        "wind_direction_100m_previous_day1": [270, 275],
    }}}  # fmt: skip
    obs = open_meteo.to_observations(body)
    ws = [o for o in obs if o["series_id"] == "openmeteo.horns_rev.ws100_d1"]
    assert len(ws) == 1  # a missing value is no row, never 0
    hour = datetime(2026, 10, 1, 12, tzinfo=UTC)
    assert ws[0]["observed_for"] == hour
    assert ws[0]["published_at"] == hour - timedelta(hours=21)
    assert ws[0]["vintage_quality"] == "estimated"
    assert len([o for o in obs if o["series_id"].endswith("wd100_d1")]) == 2


def test_every_series_is_in_the_table(db):
    known = {r[0] for r in db.execute("select series_id from series").fetchall()}
    wanted = {
        open_meteo.series_id(p, v)
        for p in open_meteo.POINTS
        for v in open_meteo.VARIABLES
    }
    assert wanted <= known
