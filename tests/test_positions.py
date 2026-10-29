from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from nordcast import positions

T0 = datetime(2026, 7, 1, tzinfo=UTC)


def calls(n=2000, seed=1, **override):
    rng = np.random.default_rng(seed)
    point = rng.normal(-50, 150, n)
    idx = pd.DatetimeIndex([T0 + timedelta(minutes=15 * k) for k in range(n)])
    df = pd.DataFrame(
        {"point": point, "q10": point - 100, "q90": point + 100, "steps_ahead": 4},
        index=idx,
    )
    return df.assign(**override)


def test_a_missing_or_empty_input_raises_never_a_flat_series():
    with pytest.raises(positions.MissingInput, match="absent"):
        positions.build_positions("forecast", calls().drop(columns="q90"), 15)
    with pytest.raises(positions.MissingInput, match="empty"):
        positions.build_positions("forecast", calls(point=np.nan), 15)


def test_a_missing_call_is_no_position_not_a_zero():
    c = calls()
    c.iloc[1500, c.columns.get_loc("point")] = np.nan
    pos = positions.build_positions("forecast", c, 15)
    assert np.isnan(pos.iloc[1500])


def test_direction_follows_the_call_and_size_stays_inside_the_limit():
    pos = positions.build_positions("forecast", calls(), 15).dropna()
    c = calls().loc[pos.index]
    moving = pos != 0
    assert (np.sign(pos[moving]) == np.sign(c.point[moving])).all()
    assert pos.abs().max() <= positions.SIZE_MW


def test_no_position_where_the_band_includes_zero():
    c = calls(q10=-1.0, q90=1.0)
    pos = positions.build_positions("forecast", c, 15).dropna()
    assert (pos == 0).all()


def test_a_stale_feed_caps_the_position():
    fresh = positions.build_positions("forecast", calls(), 15).dropna()
    stale = positions.build_positions("forecast", calls(steps_ahead=5), 15).dropna()
    assert stale.abs().max() <= 0.25 * positions.SIZE_MW + 1e-9
    assert fresh.abs().max() > 0.25 * positions.SIZE_MW


def test_a_later_call_never_changes_an_earlier_position():
    base = calls()
    changed = base.copy()
    changed.iloc[1800:, changed.columns.get_loc("point")] *= 10
    a = positions.build_positions("forecast", base, 15)
    b = positions.build_positions("forecast", changed, 15)
    pd.testing.assert_series_equal(a.iloc[:1800], b.iloc[:1800])


def test_the_control_reads_persistence_columns():
    c = calls()
    c = c.assign(pers_point=c.point, pers_q10=c.q10, pers_q90=c.q90)
    a = positions.build_positions("forecast", c, 15).rename(None)
    b = positions.build_positions("persistence", c, 15).rename(None)
    pd.testing.assert_series_equal(a, b)


def test_a_feed_stale_by_two_isps_or_more_means_no_position():
    two_behind = positions.build_positions(
        "forecast", calls(steps_ahead=6), 15
    ).dropna()
    assert (two_behind == 0).all()
