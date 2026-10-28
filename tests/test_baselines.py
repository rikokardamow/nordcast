from datetime import UTC, datetime, timedelta

import pytest

from nordcast import baselines

ASOF = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
ISP = timedelta(minutes=15)


def fake_history(volume, direction):
    data = {baselines.TARGET: volume, baselines.DIRECTION: direction}

    def history(series_id, from_ts, to_ts, asof):
        return {t: v for t, v in data[series_id].items() if from_ts <= t < to_ts}

    return history


def series(days, f, last=ASOF - 2 * ISP):
    n = days * 96
    return {last - k * ISP: f(k) for k in range(n)}


def test_persistence_is_the_latest_known_isp_with_a_band():
    vol = series(8, lambda k: (k % 7) * 10 - 30)
    call = baselines.persistence(fake_history(vol, {}), ASOF + 2 * ISP, ASOF)
    assert call["point"] == vol[ASOF - 2 * ISP]
    assert call["q10"] <= call["point"] <= call["q90"]
    assert call["steps"] == 4


def test_stale_or_missing_history_raises_instead_of_guessing():
    old = series(8, lambda k: 1.0, last=ASOF - timedelta(hours=3))
    with pytest.raises(baselines.MissingData):
        baselines.persistence(fake_history(old, {}), ASOF + ISP, ASOF)
    with pytest.raises(baselines.MissingData):
        baselines.persistence(fake_history({}, {}), ASOF + ISP, ASOF)


def test_ar1_reverts_towards_the_mean():
    vol = series(8, lambda k: 100.0 if k == 0 else (50.0 if k % 2 else -50.0))
    call = baselines.persistence_ar1(fake_history(vol, {}), ASOF + 2 * ISP, ASOF)
    assert 0 <= call["phi"] <= 1
    assert call["point"] < 100


def test_direction_persistence_is_one_hot():
    d = series(8, lambda k: -1)
    call = baselines.direction_persistence(fake_history({}, d), ASOF + ISP, ASOF)
    assert (call["direction"], call["p_down"], call["p_up"], call["p_none"]) == (
        "down",
        1,
        0,
        0,
    )


def test_climatology_counts_the_target_hour_and_sums_to_one():
    # up at 13:00 Copenhagen, down otherwise; the 28 days cross the 25 Oct
    # clock change, so the hour is Copenhagen's, not UTC's
    d = series(28, lambda k: 0)
    d = {t: (1 if t.astimezone(baselines.COPENHAGEN).hour == 13 else -1) for t in d}
    target = datetime(2026, 10, 28, 12, 30, tzinfo=UTC)
    call = baselines.direction_climatology(fake_history({}, d), target, ASOF)
    assert call["direction"] == "up"
    assert round(call["p_up"] + call["p_down"] + call["p_none"], 4) == 1
    assert call["p_none"] > 0
