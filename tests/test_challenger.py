from datetime import UTC, datetime, timedelta

import pytest

from nordcast import baselines, challenger, features

ISP = timedelta(minutes=15)
T0 = datetime(2026, 10, 20, 12, tzinfo=UTC)


def test_nominal_hides_a_value_until_its_lag_has_passed():
    # SatisfiedDemand's nominal lag: 15 min after the ISP ends
    def history(sid, from_ts, to_ts, asof):
        return {T0: 10.0, T0 + ISP: 20.0}

    view = challenger.nominal(history)
    assert view(baselines.TARGET, T0, T0 + 2 * ISP, T0 + 2 * ISP) == {T0: 10.0}
    assert view(baselines.TARGET, T0, T0 + 2 * ISP, T0 + 3 * ISP) == {
        T0: 10.0,
        T0 + ISP: 20.0,
    }
    assert view("not.a.series", T0, T0, T0) == {T0: 10.0, T0 + ISP: 20.0}


def test_nominal_returns_floats_like_training():
    # store.history_asof returns Decimal; features.sd_std8 can't raise one to 0.5
    from decimal import Decimal

    view = challenger.nominal(lambda *_: {T0: Decimal("1.5")})
    (v,) = view(baselines.TARGET, T0, T0, T0 + 2 * ISP).values()
    assert type(v) is float


def test_live_features_match_a_training_row():
    """Live, with exact first prints 10 min after each ISP; training, the
    nominal 15. Through nominal() at the training freeze time, both see the
    same target lags."""
    target = T0 + 8 * ISP
    exact, estimated = [], []
    for k in range(1, 25):
        t = target - k * ISP
        exact.append((baselines.TARGET, t, float(k), t + ISP + timedelta(minutes=10)))
        estimated.append(
            (baselines.TARGET, t, float(k), t + ISP + timedelta(minutes=15))
        )
    live = features.PointInTime(exact)
    train = features.PointInTime(estimated)
    now = features.freeze_time(target, 15) + timedelta(minutes=3)
    asof = min(now, features.freeze_time(target, 15))
    got = features.features(challenger.nominal(live.history), target, 15, asof)
    want = features.features(
        train.history, target, 15, features.freeze_time(target, 15)
    )
    assert got == want
    raw = features.features(live.history, target, 15, now)
    assert raw["steps_ahead"] < want["steps_ahead"]  # what nominal() is for


def test_the_saved_models_load_and_call():
    pytest.importorskip("lightgbm")
    if not (challenger.MODELS / f"manifest-{challenger.TAG}.json").exists():
        pytest.skip("no trained models here (jobs/train.py)")
    fitted = challenger.load()
    assert sorted(fitted) == [15, 30, 60]
    target = T0 + 8 * ISP
    rows = [(baselines.TARGET, T0 - k * ISP, float(k * 10 - 50), T0 - k * ISP + 2 * ISP)
            for k in range(24)]  # fmt: skip
    call = challenger.lightgbm(fitted)(
        features.PointInTime(rows).history, target, target - timedelta(minutes=17), 15
    )
    assert call["q10"] <= call["q50"] <= call["q90"]
    assert sum(call[f"p_{c}"] for c in ("up", "down", "none")) == pytest.approx(1)
    assert call["model_version"].startswith("lightgbm-v1@")


def test_a_tampered_model_is_refused(tmp_path):
    (tmp_path / "manifest-x.json").write_text('{"models": {"h15": {"sha256": "00"}}}')
    (tmp_path / "x-h15.pkl").write_bytes(b"not the model")
    with pytest.raises(challenger.ModelMismatch):
        challenger.load(tmp_path, "x")
