import random
from datetime import UTC, datetime, timedelta

import pytest

from nordcast import store

SERIES = "energinet.dk1.satisfied_demand"
ISP = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
FIRST_PRINT = ISP + timedelta(minutes=20)
REVISION = ISP + timedelta(hours=2)


@pytest.fixture
def two_vintages(db):
    db.execute(
        "insert into observation (series_id, observed_for, value, published_at)"
        " values (%s, %s, -86, %s), (%s, %s, -90, %s)",
        (SERIES, ISP, FIRST_PRINT, SERIES, ISP, REVISION),
    )
    return db


def test_first_print_then_revision_and_nothing_early(two_vintages):
    at = lambda t: store.value_asof(two_vintages, SERIES, ISP, t)
    assert at(FIRST_PRINT - timedelta(seconds=1)) is None
    assert at(FIRST_PRINT) == -86
    assert at(REVISION - timedelta(seconds=1)) == -86
    assert at(REVISION) == -90


def test_history_asof_equals_looping_value_asof(db):
    rng = random.Random(7)
    start = ISP - timedelta(hours=12)
    periods = [start + timedelta(minutes=15 * k) for k in range(48)]
    for p in periods:
        if rng.random() < 0.1:
            continue  # a gap
        for v in range(rng.randint(1, 3)):  # 1-3 vintages each
            db.execute(
                "insert into observation (series_id, observed_for, value, published_at)"
                " values (%s, %s, %s, %s)",
                (SERIES, p, rng.randint(-300, 300),
                 p + timedelta(minutes=20 + 60 * v + rng.randint(0, 30))),
            )  # fmt: skip
    for asof in [start, ISP, ISP + timedelta(hours=1), ISP + timedelta(days=1)]:
        bulk = store.history_asof(
            db, SERIES, start, periods[-1] + timedelta(minutes=15), asof
        )
        loop = {p: store.value_asof(db, SERIES, p, asof) for p in periods}
        assert bulk == {p: v for p, v in loop.items() if v is not None}


def test_browser_api_cannot_call_either(two_vintages):
    two_vintages.execute("set local role anon")
    with pytest.raises(Exception, match="permission denied"):
        store.history_asof(two_vintages, SERIES, ISP, REVISION, REVISION)
