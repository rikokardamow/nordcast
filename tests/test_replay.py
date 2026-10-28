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
