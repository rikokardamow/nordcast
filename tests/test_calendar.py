import itertools
from datetime import UTC, date, datetime, timedelta

import pytest

from nordcast.calendar import isp_release, isp_releases, isps


@pytest.mark.parametrize(
    "day, n",
    [(date(2026, 3, 29), 92), (date(2026, 10, 25), 100), (date(2026, 10, 28), 96)],
)
def test_isps_in_a_copenhagen_day(day, n):
    starts = isps(day)
    assert len(starts) == n
    assert all(b - a == timedelta(minutes=15) for a, b in itertools.pairwise(starts))


def test_day_starts_at_copenhagen_midnight():
    assert isps(date(2026, 10, 25))[0] == datetime(2026, 10, 24, 22, 0, tzinfo=UTC)
    assert isps(date(2026, 10, 26))[0] == datetime(2026, 10, 25, 23, 0, tzinfo=UTC)


def test_due_one_minute_before_start():
    r = isp_release(datetime(2026, 10, 28, 12, 0, tzinfo=UTC))
    assert r.scheduled_at == datetime(2026, 10, 28, 11, 59, tzinfo=UTC)
    assert r.scheduled_local == datetime(2026, 10, 28, 12, 59)
    assert r.basis == "isp"


def test_the_repeated_october_hour_keeps_distinct_deadlines():
    day = isp_releases(date(2026, 10, 25), date(2026, 10, 25))
    assert len({r.scheduled_at for r in day}) == 100
    # 02:14 Copenhagen happens twice; the two ISPs are an hour apart in UTC.
    twice = [r for r in day if r.scheduled_local == datetime(2026, 10, 25, 2, 14)]
    assert [r.scheduled_at.hour for r in twice] == [0, 1]
