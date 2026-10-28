import psycopg
import pytest

SERIES = "energinet.dk1.satisfied_demand"
ISP = "2026-10-28 12:00+00"
INSERT = (
    "insert into observation (series_id, observed_for, value, published_at)"
    f" values ('{SERIES}', %s, %s, %s)"
    " on conflict (series_id, observed_for, payload_hash) do nothing"
)
FIRST_PRINT = "2026-10-28 12:20+00"


def count(db):
    return db.execute(
        "select count(*) from observation where series_id = %s", (SERIES,)
    ).fetchone()[0]


def test_same_pull_twice_adds_nothing(db):
    db.execute(INSERT, (ISP, -86, FIRST_PRINT))
    db.execute(INSERT, (ISP, "-86.000", "2026-10-28 12:21+00"))
    assert count(db) == 1


def test_hash_does_not_depend_on_the_session_time_zone(db):
    db.execute(INSERT, (ISP, -86, FIRST_PRINT))
    db.execute("set local timezone = 'Europe/Copenhagen'")
    db.execute(INSERT, ("2026-10-28 13:00+01", -86, "2026-10-28 12:21+00"))
    assert count(db) == 1


def test_revision_is_a_second_vintage(db):
    db.execute(INSERT, (ISP, -86, FIRST_PRINT))
    db.execute(INSERT, (ISP, -90, "2026-10-28 14:00+00"))
    assert count(db) == 2


def test_a_revision_back_to_an_earlier_value_is_kept(db):
    db.execute(INSERT, (ISP, -86, FIRST_PRINT))
    db.execute(INSERT, (ISP, -90, "2026-10-28 14:00+00"))
    db.execute(INSERT, (ISP, -86, "2026-10-28 16:00+00"))
    assert count(db) == 3


@pytest.mark.parametrize(
    "sql",
    [
        "update observation set value = 1",
        "delete from observation",
        "truncate observation",
    ],
)
def test_rows_cannot_be_changed(db, sql):
    db.execute(INSERT, (ISP, -86, FIRST_PRINT))
    with pytest.raises(psycopg.errors.RaiseException, match="insert-only"):
        db.execute(sql)


def test_browser_api_cannot_read_observations(db):
    db.execute(INSERT, (ISP, -86, FIRST_PRINT))
    db.execute("set local role anon")
    assert db.execute("select count(*) from observation").fetchone() == (0,)
