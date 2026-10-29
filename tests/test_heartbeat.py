import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from nordcast import freeze, heartbeat, schedule

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
MOD = Path(heartbeat.__file__)


def beat(written, last_freeze, pull=None):
    return {
        "generated_at": written.isoformat(),
        "last_freeze_at": last_freeze.isoformat(),
        "archive_last_pull": {"mfrr_request": (pull or written).isoformat()},
    }


def test_a_fresh_heartbeat_with_a_recent_freeze_passes():
    assert (
        heartbeat.problems(
            beat(NOW - timedelta(minutes=70), NOW - timedelta(minutes=80)), NOW
        )
        == []
    )


def test_the_deadman_fails_on_a_quiet_mac_or_stalled_freezes():
    assert heartbeat.problems(
        beat(NOW - timedelta(minutes=76), NOW - timedelta(minutes=77)), NOW
    )
    # a freeze every ~15 min plus its 5-min window: 16 min is healthy, 21 isn't
    assert heartbeat.problems(beat(NOW, NOW - timedelta(minutes=16)), NOW) == []
    assert heartbeat.problems(beat(NOW, NOW - timedelta(minutes=21)), NOW)
    assert heartbeat.problems(
        {"generated_at": NOW.isoformat(), "last_freeze_at": None}, NOW
    )


def test_the_check_runs_with_the_standard_library_only(tmp_path):
    path = tmp_path / "heartbeat.json"
    old = datetime(2026, 10, 1, tzinfo=UTC)
    path.write_text(json.dumps(beat(old, old)))
    out = subprocess.run(
        [sys.executable, "-I", str(MOD), str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 1 and "::error::heartbeat written" in out.stdout


def test_due_once_the_last_heartbeat_is_55_minutes_old(tmp_path):
    path = tmp_path / "heartbeat.json"
    assert heartbeat.due(path, NOW)
    path.write_text(json.dumps(beat(NOW, NOW)))
    assert not heartbeat.due(path, NOW + timedelta(minutes=54))
    assert heartbeat.due(path, NOW + timedelta(minutes=55))


def test_on_time_counts_calls_whose_window_has_passed(db):
    # the conftest calendar: 24-27 Oct 2026; one ISP frozen at all horizons
    (release,) = schedule.due_for_freeze(
        db, datetime(2026, 10, 26, 9, 44, tzinfo=UTC), 15
    )
    target = release[1]
    at = target + timedelta(minutes=1)  # every horizon's window has passed
    before = heartbeat.on_time(db, at, span=timedelta(minutes=75))
    assert before == {"due": 0, "frozen": 0, "rate": None}  # the record hasn't started
    row = freeze.make_row({"kind": "dk1_isp", "scheduled_at": release[2]}, target, 15, at,
                          "model", "model", "frozen", {"point": 1.0})  # fmt: skip
    db.execute(
        "set session_replication_role = replica"
    )  # past its deadline: skip the trigger
    freeze.insert(db, release[0], row)
    db.execute("set session_replication_role = origin")
    after = heartbeat.on_time(db, at, span=timedelta(minutes=75))
    # from the first freeze on: ISPs target..+15 at h15, ..+30 at h30, ..+60 at h60
    assert after == {"due": 2 + 3 + 5, "frozen": 1, "rate": 0.1}


def test_the_deadman_fails_when_the_archive_stops():
    stale = beat(NOW, NOW, pull=NOW - timedelta(minutes=16))
    (problem,) = heartbeat.problems(stale, NOW)
    assert problem.startswith("archive's last mfrr_request pull")
