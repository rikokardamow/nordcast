import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq

spec = importlib.util.spec_from_file_location(
    "archive", Path(__file__).parent.parent / "jobs" / "archive.py"
)
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)

T1 = datetime(2026, 10, 28, 18, 0, tzinfo=UTC)
T2 = datetime(2026, 10, 28, 18, 1, tzinfo=UTC)
ROWS = [
    {"TimeUTC": "2026-10-28T17:30:00", "PriceArea": "DK1", "SatisfiedDemand": -86.0},
    {"TimeUTC": "2026-10-28T17:30:00", "PriceArea": "DK2", "SatisfiedDemand": 0.0},
]


def test_rerun_adds_nothing(tmp_path):
    assert archive.append(tmp_path, "ip", "TimeUTC", ROWS, T1) == 2
    assert archive.append(tmp_path, "ip", "TimeUTC", ROWS, T2) == 0
    assert pq.read_table(tmp_path / "ip" / "2026-10-28.parquet").num_rows == 2


def test_revision_is_a_new_row_with_its_pull_time(tmp_path):
    archive.append(tmp_path, "ip", "TimeUTC", ROWS, T1)
    revised = [{**ROWS[0], "SatisfiedDemand": -90.0}]
    assert archive.append(tmp_path, "ip", "TimeUTC", revised, T2) == 1
    t = pq.read_table(tmp_path / "ip" / "2026-10-28.parquet").to_pylist()
    assert [r["pulled_at_utc"] for r in t] == [T1, T1, T2]


def test_split_by_data_day_and_new_column_tolerated(tmp_path):
    rows = [ROWS[0], {**ROWS[1], "TimeUTC": "2026-10-29T00:00:00", "New": 1}]
    assert archive.append(tmp_path, "ip", "TimeUTC", rows, T1) == 2
    archive.append(
        tmp_path, "ip", "TimeUTC", [{**ROWS[0], "TimeUTC": "2026-10-29T00:15:00"}], T2
    )
    assert pq.read_table(tmp_path / "ip" / "2026-10-29.parquet").num_rows == 2
