import hashlib
import importlib.util
import json
import sys
from datetime import timedelta
from pathlib import Path

from test_freeze_and_score import NOW, live  # noqa: F401 - the fixture

from nordcast import freeze

sys.path.insert(0, str(Path(__file__).parent.parent / "jobs"))
spec = importlib.util.spec_from_file_location(
    "stamp_daily", Path(__file__).parent.parent / "jobs" / "stamp_daily.py"
)
stamp_daily = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stamp_daily)


def test_a_finished_day_is_written_once_with_its_hash(live, tmp_path, monkeypatch):  # noqa: F811
    db, release = live
    rows = freeze.freeze_rows(db, release, 15, NOW)
    monkeypatch.setattr(stamp_daily, "FROZEN", tmp_path)
    monkeypatch.setattr(stamp_daily.stamp, "stamp", lambda path: None)  # no calendars
    today = stamp_daily.today_copenhagen(NOW)
    assert stamp_daily.unstamped_days(db, today) == []  # today isn't finished
    (day,) = stamp_daily.unstamped_days(db, today + timedelta(days=1))
    path, sha = stamp_daily.write_day(db, day)
    written = json.loads(path.read_text())
    assert [r["sha256"] for r in written] == [r["sha256"] for r in rows]
    assert sha.read_text().split()[0] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert stamp_daily.unstamped_days(db, today + timedelta(days=1)) == []
