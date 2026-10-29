from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from nordcast.layers.curve import (
    cushing_utilisation,
    physical_bands,
    roll_pressure_seasonal,
    rolling_quantile_bands,
    tas_window_flag,
    utilisation_decile,
)


def test_cushing_utilisation_spec_worked_example() -> None:
    stocks = pd.Series([50000.0], index=[pd.Timestamp("2026-01-01")])
    capacity = pd.Series([78000.0], index=[pd.Timestamp("2026-01-01")])
    util = cushing_utilisation(stocks, capacity)
    assert util.iloc[0] == pytest.approx(0.641, abs=1e-3)


def test_cushing_utilisation_real_eia_cross_check() -> None:
    """Real 2024-03-01 values read directly from EIA's own crudeoilstorage.xlsx (Cushing
    sheet, downloaded and inspected live this session): stocks=33086 (Pipeline and Tank
    Farm), working_cap=80604 (Sum of Working Storage Capacity and Stocks in Transit).
    Feeding both to this function must reproduce EIA's own published Alternate
    Utilization Rate (0.4104759069028832) to within 1e-4 -- a real, independent-source
    cross-check, not a synthetic one."""
    stocks = pd.Series([33086.0], index=[pd.Timestamp("2024-03-01")])
    capacity = pd.Series([80604.0], index=[pd.Timestamp("2024-03-01")])
    util = cushing_utilisation(stocks, capacity)
    assert util.iloc[0] == pytest.approx(0.4104759069028832, abs=1e-4)


def test_cushing_utilisation_forward_fills_sparse_semi_annual_capacity() -> None:
    """working_cap_kbbl is sparse (semi-annual, matching the real
    eia.cushing_working_capacity series); stocks_kbbl is dense (weekly). The semi-annual
    value must be forward-filled onto every weekly date, never the other way round."""
    stocks = pd.Series(
        [50000.0, 51000.0, 52000.0],
        index=pd.to_datetime(["2026-01-05", "2026-01-12", "2026-01-19"]),
    )
    capacity = pd.Series([78000.0], index=[pd.Timestamp("2026-01-01")])
    util = cushing_utilisation(stocks, capacity)
    assert util.tolist() == pytest.approx([50000 / 78000, 51000 / 78000, 52000 / 78000])


def test_utilisation_decile_is_always_in_1_to_10() -> None:
    dates = pd.bdate_range("2020-01-01", periods=300)
    rng = np.random.default_rng(0)
    util = pd.Series(rng.uniform(0.3, 0.9, size=len(dates)), index=dates)
    decile = utilisation_decile(util, years=1)
    assert decile.between(1, 10).all()


def test_roll_pressure_seasonal_detects_a_real_seasonal_difference() -> None:
    dates = pd.bdate_range("2026-01-01", "2026-12-31")
    rng = np.random.default_rng(2)
    daily_move = pd.Series(rng.normal(0.0, 0.05, size=len(dates)), index=dates)
    flag = pd.Series(False, index=dates)

    # A deliberately larger daily move inside a hand-constructed "roll window" than
    # outside it (plus real noise, so variance isn't zero and a real t-stat exists), so
    # the function must detect mean_in != mean_out with real t-stats.
    window_dates = dates[(dates.day >= 5) & (dates.day <= 9)]
    flag.loc[window_dates] = True
    daily_move.loc[window_dates] += 1.0
    s12 = daily_move.cumsum()

    result = roll_pressure_seasonal(s12, flag)
    row = result[result["year"] == 2026].iloc[0]
    assert row["mean_in"] > row["mean_out"]
    assert not np.isnan(row["t_in"])


def test_physical_bands_quantiles_are_ordered_and_centred() -> None:
    dates = pd.bdate_range("2020-01-01", periods=500)
    rng = np.random.default_rng(1)
    diff = pd.Series(rng.normal(0.0, 1.0, size=len(dates)), index=dates)
    bands = physical_bands(diff, window=250)

    tail = bands.iloc[300:]
    assert (tail["p05"] <= tail["p50"]).all()
    assert (tail["p50"] <= tail["p95"]).all()
    assert tail["p50"].mean() == pytest.approx(0.0, abs=0.5)


def test_rolling_quantile_bands_respects_min_periods() -> None:
    # The curve page's convexity band uses min_periods=20: nothing before the 20th
    # observation should be scored at all, rather than ranked against a handful of points.
    dates = pd.bdate_range("2020-01-01", periods=100)
    rng = np.random.default_rng(2)
    series = pd.Series(rng.normal(0.0, 1.0, size=len(dates)), index=dates)

    bands = rolling_quantile_bands(series, window=252, min_periods=20)

    assert bands["p05"].iloc[:19].isna().all()
    assert bands["p05"].iloc[19:].notna().all()
    assert (bands["value"] == series).all()


def test_physical_bands_matches_the_shared_helper_at_min_periods_one() -> None:
    dates = pd.bdate_range("2020-01-01", periods=300)
    rng = np.random.default_rng(3)
    diff = pd.Series(rng.normal(0.0, 1.0, size=len(dates)), index=dates)

    pd.testing.assert_frame_equal(
        physical_bands(diff, window=250),
        rolling_quantile_bands(diff, window=250, min_periods=1),
    )


def test_tas_window_flag_flags_exactly_the_last_two_business_days_before_expiry() -> None:
    expiry = pd.Timestamp("2026-01-20")  # a Tuesday
    day1 = pd.Timestamp(np.busday_offset(expiry.date(), -1, roll="backward"))
    day2 = pd.Timestamp(np.busday_offset(expiry.date(), -2, roll="backward"))

    dates = pd.bdate_range("2026-01-10", "2026-01-25")
    flag = tas_window_flag(dates, pd.Series([expiry]))

    for d in dates:
        expected = d in (day1, day2)
        assert bool(flag.loc[d]) == expected, d
