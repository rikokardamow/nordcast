from datetime import UTC, datetime

import psycopg
import pytest

from nordcast import store
from nordcast.calendar import Release, isp_release


def day_count(db, local_day):
    return db.execute(
        "select count(distinct scheduled_at) from release where release_kind = 'dk1_isp'"
        " and (period_end at time zone 'Europe/Copenhagen')::date = %s",
        (local_day,),
    ).fetchone()[0]


def test_release_table_has_every_isp_with_distinct_deadlines(db):
    assert day_count(db, "2026-10-25") == 100
    assert day_count(db, "2026-10-26") == 96


def test_reloading_changes_nothing(db):
    before = db.execute("select count(*) from release").fetchone()[0]
    store.load_releases(
        db,
        "energinet",
        "dk1_isp",
        [isp_release(datetime(2026, 10, 26, 8, 0, tzinfo=UTC))],
    )
    assert db.execute("select count(*) from release").fetchone()[0] == before


def test_scheduled_at_that_disagrees_with_local_time_is_refused(db):
    good = isp_release(datetime(2030, 1, 1, 8, 0, tzinfo=UTC))
    bad = Release(good.period_end, good.scheduled_local, good.period_end)
    with pytest.raises(psycopg.errors.RaiseException, match="is not"):
        store.load_releases(db, "energinet", "dk1_isp", [bad])


def test_a_call_after_the_deadline_is_refused(db):
    rid = db.execute(
        "select release_id from release where release_kind = 'dk1_isp' limit 1"
    ).fetchone()[0]
    with pytest.raises(psycopg.errors.RaiseException, match="too late"):
        db.execute(
            "insert into forecast (release_id, series_id, target_period, source_kind,"
            " method, status, point, horizon_min, data_cutoff, sha256, payload)"
            " values (%s, 'energinet.dk1.satisfied_demand', now(), 'baseline',"
            " 'persistence', 'frozen', 10, 15, now(), 'x', '{}')",
            (rid,),
        )
