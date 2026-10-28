import random
from datetime import UTC, datetime, timedelta

import pytest

from nordcast import features, store
from nordcast.baselines import DIRECTION, TARGET, MissingData

ISP = timedelta(minutes=15)
T = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


def synthetic_rows(seed=1, days=2):
    """Every feature series with 1-2 vintages per ISP, some published late."""
    rng = random.Random(seed)
    rows = []
    start = T - timedelta(days=days)
    for k in range(days * 96 + 8):
        t = start + k * ISP
        for sid in features.SERIES:
            if rng.random() < 0.05:
                continue  # gaps
            is_fc = "_fc_" in sid or sid.endswith("da_price_eur")
            pub = (
                t - timedelta(hours=6)
                if is_fc
                else t + ISP + timedelta(minutes=rng.randint(5, 40))
            )
            value = [1, -1, 0][k % 3] if sid == DIRECTION else rng.uniform(-300, 300)
            rows.append((sid, t, value, pub))
            if rng.random() < 0.2:  # a revision, later
                rows.append((sid, t, value + 7, pub + timedelta(hours=2)))
    return rows


@pytest.mark.parametrize("horizon", [15, 30, 60])
def test_no_feature_reads_anything_published_after_the_freeze(horizon):
    pit = features.PointInTime(synthetic_rows())
    asof = features.freeze_time(T, horizon)
    calls = []

    def guarded(sid, from_ts, to_ts, at):
        assert at <= asof, f"{sid} read as of {at}, after the freeze at {asof}"
        calls.append(sid)
        out = pit.history(sid, from_ts, to_ts, at)
        # and nothing it hands back was published after the freeze
        for period, v in out.items():
            assert pit.value(sid, period, asof) == v
        return out

    f = features.features(guarded, T, horizon, asof)
    assert len(calls) > 10
    assert f["horizon_min"] == horizon
    assert f["sd_lag1"] is not None


def test_a_value_published_after_the_freeze_never_changes_a_feature():
    rows = synthetic_rows()
    asof = features.freeze_time(T, 15)
    before = features.features(features.PointInTime(rows).history, T, 15, asof)
    later = [(s, p, v + 1000, asof + timedelta(seconds=1)) for s, p, v, _ in rows]
    after = features.features(features.PointInTime(rows + later).history, T, 15, asof)
    assert before == after


def test_no_target_history_raises_instead_of_guessing():
    with pytest.raises(MissingData):
        features.features(features.PointInTime([]).history, T, 15, T)


def test_point_in_time_equals_the_database(db):
    rows = [r for r in synthetic_rows(seed=3, days=1) if r[0] in (TARGET, DIRECTION)]
    store.insert_observations(
        db,
        [{"series_id": s, "observed_for": p, "value": round(v, 4), "published_at": pub,
          "vintage_quality": "exact"} for s, p, v, pub in rows],
    )  # fmt: skip
    pit = features.load(
        db, T - timedelta(days=2), T + timedelta(days=1), [TARGET, DIRECTION]
    )
    for asof in [
        T - timedelta(hours=20),
        T - timedelta(hours=3),
        T,
        T + timedelta(hours=5),
    ]:
        frm, to = T - timedelta(days=1), T + timedelta(hours=2)
        for sid in (TARGET, DIRECTION):
            db_side = {
                p: float(v)
                for p, v in store.history_asof(db, sid, frm, to, asof).items()
            }
            assert pit.history(sid, frm, to, asof) == pytest.approx(db_side)
