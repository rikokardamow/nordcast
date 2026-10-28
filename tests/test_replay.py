import itertools
from datetime import timedelta

import pandas as pd

from nordcast import replay


def frame():
    start = replay.ROUNDS["2025q4"][0]
    targets = [start + timedelta(minutes=15 * k) for k in range(-10, 96 * 400)]
    return pd.DataFrame({"target": targets, "y": 0.0})


def test_rounds_are_consecutive_copenhagen_quarters():
    bounds = list(replay.ROUNDS.values())
    assert all(a[1] == b[0] for a, b in itertools.pairwise(bounds))
    assert all(s.hour == 0 and s.day == 1 for s, _ in bounds)


def test_a_round_trains_only_on_isps_before_it():
    df = frame()
    for name, (start, end) in replay.ROUNDS.items():
        train, rows = replay.training_rows(df, name), replay.round_rows(df, name)
        assert train.target.max() < start <= rows.target.min()
        assert rows.target.max() < end


def test_scorecard_has_every_column_the_log_reports():
    rows = pd.DataFrame({"y": [10.0, -10.0], "y_dir": ["up", "down"],
                         "imb_price": [1.0, 1.0], "da_price_target": [1.0, 1.0]})  # fmt: skip
    pred = pd.DataFrame({"q10": [0.0, -20.0], "q50": [5.0, -5.0], "q90": [20.0, 0.0],
                         "p_down": [0.0, 1.0], "p_none": [0.0, 0.0], "p_up": [1.0, 0.0]})  # fmt: skip
    s = replay.scorecard(rows, pred)
    assert {
        "mae",
        "rmse",
        "pinball",
        "coverage",
        "direction_acc",
        "brier",
        "sign",
        "pnl_eur",
    } <= set(s)
    assert s["sign"] == 1 and s["direction_acc"] == 1 and s["coverage"] == 1


def test_an_isp_a_method_could_not_forecast_is_counted_not_filled():
    rows = pd.DataFrame({"y": [10.0, -10.0], "y_dir": ["up", "down"],
                         "imb_price": [1.0, 1.0], "da_price_target": [1.0, 1.0]})  # fmt: skip
    pred = pd.DataFrame({"q10": [0.0, None], "q50": [10.0, None], "q90": [20.0, None],
                         "p_down": [0.0, 1.0], "p_none": [0.0, 0.0], "p_up": [1.0, 0.0]})  # fmt: skip
    s = replay.scorecard(rows, pred)
    assert s["missing"] == 1 and s["n"] == 1 and s["mae"] == 0


def test_the_linear_rung_fits_only_on_labels_a_day_old():
    from datetime import datetime

    start = datetime(2026, 7, 6, tzinfo=replay.CPH)  # a Monday, Copenhagen
    t = [start - timedelta(days=30) + timedelta(minutes=15 * k) for k in range(96 * 37)]
    rng = __import__("numpy").random.default_rng(1)
    lag = rng.normal(size=len(t))
    df = pd.DataFrame({"target": pd.to_datetime(t), "y": 2 * lag, "sd_lag1": lag,
                       "sd_lag2": 0.0, "sd_lag3": 0.0, "sd_lag4": 0.0, "sd_mean4": 0.0,
                       "regime_activated": 1.0, "hour": 1, "quarter": 0, "weekday": 0,
                       "pers_q10": 0.0, "pers_point": 0.0, "pers_q90": 0.0, "pers_dir": "up"})  # fmt: skip
    rows = df[(df.target >= start) & (df.target < start + timedelta(days=7))]
    # labels less than a day old at the week's start are poisoned: a fit that used them would show it
    poisoned = df.copy()
    poisoned.loc[poisoned.target >= start - replay.LABEL_DELAY, "y"] = 1e6
    pred = replay.linear_lags_calendar(rows, None, {"all": poisoned})
    assert (pred.q50 - 2 * rows.sd_lag1).abs().max() < 1e-6
