from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from nordcast import model


def frame(n=10):
    t0 = datetime(2025, 10, 1, tzinfo=UTC)
    return pd.DataFrame(
        {
            "target": [t0 + timedelta(minutes=15 * k) for k in range(n)][::-1],
            "y": range(n),
            "y_dir": "up",
            "imb_price": 1.0,
            "da_price_target": 1.0,
        }
    )


def test_split_is_in_time_order_60_20_20():
    fit, cal, val = model.split(frame())
    assert (len(fit), len(cal), len(val)) == (6, 2, 2)
    assert fit.target.max() < cal.target.min() <= cal.target.max() < val.target.min()


def test_pnl_is_long_on_up_short_on_down_flat_on_none():
    df = pd.DataFrame({"imb_price": [150.0, 20.0, 80.0, np.nan],
                       "da_price_target": [100.0, 100.0, 100.0, 100.0]})  # fmt: skip
    called = np.array(["up", "down", "none", "up"])
    # 10 MW x 0.25 h: +50 x 2.5 + 80 x 2.5 + 0; the unpriced ISP is left out
    assert model.pnl(df, called) == pytest.approx(125 + 200)


def test_pinball_and_brier():
    assert model.pinball([10.0], [0.0], 0.9) == pytest.approx(9.0)
    assert model.pinball([0.0], [10.0], 0.9) == pytest.approx(1.0)
    probs = np.array([[0.0, 0.0, 1.0]])  # all on up
    assert model.brier(probs, ["up"]) == 0
    assert model.brier(probs, ["down"]) == 2


def test_features_never_include_labels_or_the_baseline():
    df = pd.DataFrame([{c: 1.0 for c in model.FEATURES_DROP} | {"sd_lag1": 1.0}])
    assert list(model.X(df).columns) == ["sd_lag1"]


def test_the_final_model_uses_the_whole_window(monkeypatch):
    seen = []
    monkeypatch.setattr(
        model,
        "_fit",
        lambda h, params, fit, cal: seen.append((len(fit), len(cal))) or Stub(),
    )
    model.select_and_fit(frame(10), 15, grid=[model.GRID[0]])
    assert seen[-1] == (8, 2)  # boosters on 80 %, calibration on the last 20 %


class Stub:
    def predict(self, df):
        return pd.DataFrame({"q10": 0.0, "q50": 0.0, "q90": 0.0, "p_down": 1 / 3,
                             "p_none": 1 / 3, "p_up": 1 / 3}, index=df.index)  # fmt: skip


def test_a_later_start_keeps_the_same_validation_slice():
    df = frame(100)
    since = df.target.sort_values().iloc[50]
    _, _, val = model.split(df)
    fit, cal, val2 = model.split_since(df, since)
    assert val2.equals(val)
    assert fit.target.min() >= since and len(fit) + len(cal) == 30
