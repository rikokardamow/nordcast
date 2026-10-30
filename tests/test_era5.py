import importlib.util
from datetime import UTC, date, datetime
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from nordcast.sources import era5, open_meteo

spec = importlib.util.spec_from_file_location(
    "backfill_era5", Path(__file__).parent.parent / "jobs" / "backfill_era5.py"
)
job = importlib.util.module_from_spec(spec)
spec.loader.exec_module(job)

HOUR = datetime(2026, 1, 1, tzinfo=UTC)


def test_wind_speed_is_the_length_of_the_vector():
    assert era5.wind_speed(3.0, -4.0) == 5.0


def test_series_ids_are_named_era5_so_they_cannot_pass_for_forecasts():
    assert era5.series_id("horns_rev") == "era5.horns_rev.ws100"


def test_the_area_holds_the_nearest_cell_of_every_point():
    north, west, south, east = era5.area()
    assert (north, west, south, east) == (57.75, 7.75, 55.25, 11.25)
    for lat, lon in open_meteo.POINTS.values():
        assert south - era5.GRID / 2 <= lat <= north + era5.GRID / 2
        assert west - era5.GRID / 2 <= lon <= east + era5.GRID / 2


def test_a_month_request_has_every_day_and_hour():
    req = era5.request(2024, 2)
    assert req["day"][-1] == "29"
    assert len(req["time"]) == 24
    assert era5.request(2024, 2, days=[1])["day"] == ["01"]


def test_a_point_reads_its_nearest_cell():
    # latitudes run north to south in ERA5 files
    rows = era5.to_rows(
        [HOUR],
        [55.75, 55.5, 55.25],
        [7.75, 8.0],
        [[[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]],
        [[[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]],
        points={"p": (55.48, 7.87)},
    )
    assert rows == [{"series_id": "era5.p.ws100", "observed_for": HOUR,
                     "value": 3.0, "u100": 3.0, "v100": 0.0}]  # fmt: skip


def test_a_missing_value_is_no_row_never_0():
    rows = era5.to_rows(
        [HOUR], [55.5], [8.0], [[[None]]], [[[1.0]]], points={"p": (55.5, 8.0)}
    )
    assert rows == []


def test_only_ended_months_are_fetched():
    assert list(job.months(date(2025, 11, 15), date(2026, 2, 1))) == [
        (2025, 11),
        (2025, 12),
        (2026, 1),
    ]
    assert list(job.months(date(2026, 1, 1), date(2026, 1, 31))) == []


def test_the_licence_check_needs_the_era5_licence():
    assert not job.licence_accepted([{"id": "terms-of-use-cds", "revision": 13}])
    assert job.licence_accepted([{"id": "cc-by", "revision": 1}])


def _fake(calls):
    def retrieve(dataset, request, target):
        calls.append((dataset, request["year"][0], request["month"][0]))
        Path(target).write_text("x")

    return retrieve


def _read(path):
    return [{"series_id": "era5.p.ws100", "observed_for": HOUR, "value": 1.0,
             "u100": 1.0, "v100": 0.0}]  # fmt: skip


def test_a_rerun_sends_nothing_and_adds_0_rows(tmp_path):
    calls = []
    first, last = date(2026, 1, 1), date(2026, 3, 1)
    todo = job.missing(first, last, tmp_path)
    assert job.backfill(todo, _fake(calls), _read, tmp_path) == 2
    assert calls == [(era5.DATASET, "2026", "01"), (era5.DATASET, "2026", "02")]
    assert pq.read_table(tmp_path / "2026-01.parquet").num_rows == 1

    again = job.missing(first, last, tmp_path)
    assert again == []
    assert job.backfill(again, _fake(calls), _read, tmp_path) == 0
    assert len(calls) == 2


def test_an_error_stops_the_run_and_a_rerun_resumes_there(tmp_path):
    calls = []

    def fails_on_february(dataset, request, target):
        if request["month"] == ["02"]:
            raise RuntimeError("403 Forbidden")
        _fake(calls)(dataset, request, target)

    first, last = date(2026, 1, 1), date(2026, 4, 1)
    with pytest.raises(RuntimeError):
        job.backfill(
            job.missing(first, last, tmp_path), fails_on_february, _read, tmp_path
        )
    assert len(calls) == 1  # no retry and no March request after the failure
    assert job.missing(first, last, tmp_path) == [(2026, 2), (2026, 3)]


def test_read_netcdf_finds_the_cds_variable_names(tmp_path):
    netCDF4 = pytest.importorskip("netCDF4")
    path = tmp_path / "x.nc"
    with netCDF4.Dataset(path, "w") as ds:
        ds.createDimension("valid_time", 1)
        ds.createDimension("latitude", 1)
        ds.createDimension("longitude", 1)
        ds.createVariable("valid_time", "i8", ("valid_time",))[:] = [
            int(HOUR.timestamp())
        ]
        ds.createVariable("latitude", "f8", ("latitude",))[:] = [55.5]
        ds.createVariable("longitude", "f8", ("longitude",))[:] = [8.0]
        dims = ("valid_time", "latitude", "longitude")
        ds.createVariable("u100", "f4", dims)[:] = [[[3.0]]]
        ds.createVariable("v100", "f4", dims)[:] = [[[4.0]]]
    rows = era5.read_netcdf(path)
    assert len(rows) == len(open_meteo.POINTS)
    assert rows[0]["observed_for"] == HOUR
    assert rows[0]["value"] == pytest.approx(5.0)
