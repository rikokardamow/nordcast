import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest

from nordcast import baselines, freeze, schedule, score, store
from nordcast.calendar import RELEASE_KIND, isp_release

ISP = timedelta(minutes=15)
NOW = datetime.now(UTC).replace(second=0, microsecond=0)
TARGET = NOW + 20 * timedelta(minutes=1) - timedelta(minutes=NOW.minute % 15)
while TARGET - NOW < timedelta(minutes=15):
    TARGET += ISP


@pytest.fixture
def live(db):
    """8 days of first prints up to now, and a release for TARGET."""
    last = TARGET - 4 * ISP
    rows = []
    for k in range(8 * 96):
        t = last - k * ISP
        pub = t + ISP + timedelta(minutes=10)
        if pub > NOW:
            continue
        rows += [
            {"series_id": baselines.TARGET, "observed_for": t, "value": (k % 9) * 20 - 80,
             "published_at": pub, "vintage_quality": "exact"},
            {"series_id": baselines.DIRECTION, "observed_for": t, "value": [1, -1, 0][k % 3],
             "published_at": pub, "vintage_quality": "exact"},
        ]  # fmt: skip
    store.insert_observations(db, rows)
    store.load_releases(db, "energinet", RELEASE_KIND, [isp_release(TARGET)])
    (release,) = [
        r for r in schedule.due_for_freeze(db, TARGET - timedelta(minutes=16), 15)
    ]
    return db, release


def test_due_for_freeze_finds_the_isp_in_its_window(live):
    db, release = live
    assert release[1] == TARGET
    assert schedule.due_for_freeze(db, TARGET - timedelta(minutes=10), 15) == []


def test_freeze_writes_every_call_with_a_hash_that_checks(live):
    db, release = live
    rows = freeze.freeze_rows(db, release, 15, NOW)
    assert [(r["source_kind"], r["method"]) for r in rows] == [
        ("model", "model"),
        ("baseline", "persistence"),
        ("baseline", "persistence_ar1"),
        ("baseline", "direction_climatology"),
    ]
    for r in rows:
        body = {k: v for k, v in r.items() if k != "sha256"}
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        assert hashlib.sha256(canonical.encode()).hexdigest() == r["sha256"]
    model = rows[0]
    assert model["model_version"] == "v0-persistence"
    assert model["p_up"].count(".") == 1 and len(model["p_up"].split(".")[1]) == 4
    with pytest.raises(freeze.AlreadyFrozen):
        freeze.freeze_rows(db, release, 15, NOW)
    assert schedule.due_for_freeze(db, TARGET - timedelta(minutes=16), 15) == []


def test_a_failed_model_freezes_persistence_flagged(live):
    db, release = live

    def broken(*_):
        raise ZeroDivisionError

    rows = freeze.freeze_rows(db, release, 15, NOW, model=broken)
    assert rows[0]["status"] == "auto_baseline"
    assert rows[0]["point"] == rows[1]["point"]
    assert "ZeroDivisionError" in rows[0]["flag_reason"]


def test_score_against_the_first_print(live):
    db, release = live
    freeze.freeze_rows(db, release, 15, NOW)
    after = TARGET + ISP
    assert score.score_isp(db, TARGET, after) == ("pending", 0)
    store.insert_observations(db, [
        {"series_id": baselines.TARGET, "observed_for": TARGET, "value": 50,
         "published_at": after + timedelta(minutes=8), "vintage_quality": "exact"},
        {"series_id": baselines.DIRECTION, "observed_for": TARGET, "value": 1,
         "published_at": after + timedelta(minutes=8), "vintage_quality": "exact"},
        {"series_id": baselines.TARGET, "observed_for": TARGET, "value": 999,
         "published_at": after + timedelta(minutes=30), "vintage_quality": "exact"},
    ])  # fmt: skip
    status, n = score.score_isp(db, TARGET, after + timedelta(hours=1))
    assert (status, n) == ("scored", 4)
    got = db.execute(
        "select f.method, s.actual, s.direction_actual, s.brier is not null, s.covered is not null"
        " from score s join forecast f using (forecast_id) order by f.method"
    ).fetchall()
    assert {m: (float(a), d) for m, a, d, *_ in got}["persistence"] == (50.0, "up")
    assert score.score_isp(db, TARGET, after + timedelta(hours=2)) == ("scored", 0)


def test_losses():
    f = {"point": 10, "q10": 0, "q50": 10, "q90": 20, "direction": "up",
         "p_up": 0.6, "p_down": 0.3, "p_none": 0.1}  # fmt: skip
    out = score.losses(f, 30.0, "down")
    assert out["error"] == -20 and out["covered"] is False
    assert out["pinball_q90"] == pytest.approx(0.9 * 10)
    assert out["pinball_q10"] == pytest.approx(0.1 * 30)
    assert out["direction_hit"] is False
    assert out["brier"] == pytest.approx(0.36 + 0.49 + 0.01)


def fake_challenger(history, target, now, horizon):
    return {"point": 1.0, "q10": 0.0, "q50": 1.0, "q90": 2.0, "direction": "up",
            "p_up": 0.5, "p_down": 0.3, "p_none": 0.2, "model_version": f"fake-h{horizon}"}  # fmt: skip


def test_a_challenger_freezes_beside_the_headline(live):
    db, release = live
    rows = freeze.freeze_rows(
        db, release, 15, NOW, challengers=[("fake", fake_challenger)]
    )
    assert rows[0]["method"] == "model" and rows[0]["model_version"] == "v0-persistence"
    (c,) = [r for r in rows if r["source_kind"] == "challenger"]
    assert (c["method"], c["model_version"], c["q90"]) == ("fake", "fake-h15", "2.0")


def test_a_failed_challenger_writes_no_row_and_blocks_nothing(live):
    db, release = live

    def broken(*_):
        raise ZeroDivisionError("boom")

    missed = []
    rows = freeze.freeze_rows(
        db, release, 15, NOW, challengers=[("broken", broken)], missed=missed
    )
    assert [r["source_kind"] for r in rows].count("challenger") == 0
    assert rows[0]["status"] == "frozen"
    assert missed == ["broken: ZeroDivisionError: boom"]


@pytest.mark.parametrize(
    "probs",
    [
        (0.33335, 0.33335, 0.3333),  # each rounds up: the three sum to 1.0001
        (0.49995, 0.50005, 0.0),  # p_up + p_down round to 1.0001: p_none must stay >= 0
        (0.123456, 0.654321, 0.222223),
    ],
)
def test_probabilities_always_sum_to_one_after_rounding(probs):
    up, down, none = probs
    p = freeze._probabilities({"p_up": up, "p_down": down, "p_none": none})
    vals = [float(p[k]) for k in ("p_up", "p_down", "p_none")]
    assert abs(sum(vals) - 1) < 1e-9 and min(vals) >= 0


def test_a_challenger_row_the_database_refuses_never_blocks_the_headline(live):
    db, release = live

    def empty(history, target, now, horizon):  # no volume, no direction: refused
        return {"model_version": "empty"}

    missed = []
    rows = freeze.freeze_rows(
        db, release, 15, NOW, challengers=[("empty", empty)], missed=missed
    )
    assert rows[0]["method"] == "model"
    assert [r["source_kind"] for r in rows].count("challenger") == 0
    n = db.execute("select count(*) from forecast where method = 'model'").fetchone()[0]
    assert n == 1
    assert missed and missed[0].startswith("empty: CheckViolation")
