from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nordcast.layers.backtest import (
    backtest,
    fractionate,
    inventory_predictability_test,
    spread_to_return,
)


def _index(n: int) -> pd.DatetimeIndex:
    return pd.bdate_range("2015-01-01", periods=n)


def _returns(n: int = 500, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(0.0003, 0.02, n), index=_index(n))


# --- the spec's own acceptance tests ----------------------------------------------


def test_a_constant_long_reproduces_buy_and_hold_exactly_at_zero_cost() -> None:
    """The spec's own first acceptance test. A position of +1 held throughout, with no
    costs, must earn precisely the underlying's own log return -- no more, no less."""
    returns = _returns()
    pos = pd.Series(1.0, index=returns.index)
    result = backtest(pos, returns, cost_bps=0.0)
    # The first day is lost to the one-day position lag, so buy-and-hold starts at t=1.
    assert result.pnl.sum() == pytest.approx(returns.iloc[1:].sum(), abs=1e-12)


def test_shifting_the_returns_changes_the_pnl() -> None:
    """The spec's own look-ahead guard: if P&L were invariant to shifting the return
    series, the backtester would not actually be aligning positions to the days they
    earn."""
    returns = _returns()
    pos = pd.Series(np.sign(np.sin(np.arange(len(returns)) / 7)), index=returns.index)
    base = backtest(pos, returns, cost_bps=0.0).pnl.sum()
    shifted = backtest(pos, returns.shift(1), cost_bps=0.0).pnl.sum()
    assert base != pytest.approx(shifted)


def test_positions_are_lagged_one_day() -> None:
    """A position taken on day t earns day t+1's return, never day t's."""
    idx = _index(4)
    returns = pd.Series([0.0, 0.10, 0.0, 0.0], index=idx)
    pos = pd.Series([1.0, 0.0, 0.0, 0.0], index=idx)  # long only on day 0
    result = backtest(pos, returns, cost_bps=0.0)
    assert result.pnl.iloc[1] == pytest.approx(0.10)  # day 0's position earns day 1
    assert result.pnl.iloc[2] == pytest.approx(0.0)


# --- costs and turnover -----------------------------------------------------------


def test_costs_are_charged_on_position_changes_not_on_holdings() -> None:
    """A position held flat costs nothing to keep; only trading it costs."""
    idx = _index(5)
    returns = pd.Series(0.0, index=idx)
    held = pd.Series([1.0, 1.0, 1.0, 1.0, 1.0], index=idx)
    traded = pd.Series([1.0, -1.0, 1.0, -1.0, 1.0], index=idx)
    assert backtest(held, returns, cost_bps=10.0).pnl.sum() == pytest.approx(
        backtest(held, returns, cost_bps=0.0).pnl.sum()
    )
    assert backtest(traded, returns, cost_bps=10.0).pnl.sum() < 0


def test_turnover_scales_with_how_often_the_position_flips() -> None:
    idx = _index(100)
    returns = pd.Series(0.0, index=idx)
    quiet = backtest(pd.Series(1.0, index=idx), returns).stats["turnover"]
    busy = backtest(
        pd.Series(np.where(np.arange(100) % 2 == 0, 1.0, -1.0), index=idx), returns
    ).stats["turnover"]
    assert busy > quiet


# --- statistics -------------------------------------------------------------------


def test_stats_carry_every_field_the_spec_names() -> None:
    result = backtest(pd.Series(1.0, index=_returns().index), _returns())
    for field in (
        "ann_log_return",
        "ann_vol",
        "sharpe",
        "max_drawdown",
        "calmar",
        "hit_rate",
        "turnover",
        "n_days",
    ):
        assert field in result.stats, field


def test_sharpe_is_the_return_to_vol_ratio_with_no_risk_free_rate() -> None:
    result = backtest(pd.Series(1.0, index=_returns().index), _returns())
    stats = result.stats
    assert stats["sharpe"] == pytest.approx(stats["ann_log_return"] / stats["ann_vol"])


def test_a_steadily_rising_equity_curve_has_no_drawdown() -> None:
    idx = _index(50)
    result = backtest(
        pd.Series(1.0, index=idx), pd.Series(0.01, index=idx), cost_bps=0.0
    )
    assert result.stats["max_drawdown"] == pytest.approx(0.0)


def test_drawdown_is_measured_from_the_running_peak() -> None:
    idx = _index(4)
    returns = pd.Series([0.0, 0.10, -0.30, 0.0], index=idx)
    result = backtest(pd.Series(1.0, index=idx), returns, cost_bps=0.0)
    assert result.stats["max_drawdown"] == pytest.approx(-0.30, abs=1e-9)


def test_worst_five_days_are_reported_and_ordered() -> None:
    result = backtest(pd.Series(1.0, index=_returns().index), _returns())
    worst = result.worst_days
    assert len(worst) == 5
    assert worst.is_monotonic_increasing  # most negative first


def test_rolling_three_year_sharpe_needs_three_years_of_history() -> None:
    returns = _returns(1000)
    result = backtest(pd.Series(1.0, index=returns.index), returns)
    rolling = result.rolling_sharpe
    assert rolling.iloc[:750].isna().all()
    assert rolling.iloc[756:].notna().any()


def test_spread_pnl_overrides_the_price_return_when_supplied() -> None:
    """A calendar-spread strategy earns the change in the spread, not the front-month's
    own return -- passing spread_pnl must actually replace it."""
    idx = _index(5)
    returns = pd.Series(0.05, index=idx)
    spread = pd.Series(0.01, index=idx)
    pos = pd.Series(1.0, index=idx)
    assert backtest(
        pos, returns, spread_pnl=spread, cost_bps=0.0
    ).pnl.sum() == pytest.approx(spread.iloc[1:].sum())


# --- fractionation ----------------------------------------------------------------


def test_fractionation_shares_sum_to_one_per_condition() -> None:
    """The spec's own acceptance test: shares of total P&L must sum to 1 +/- 1e-6."""
    pnl = _returns(400)
    conditioners = {
        "regime": pd.Series(np.arange(400) % 3, index=pnl.index),
        "month": pd.Series(pnl.index.month, index=pnl.index),
    }
    table = fractionate(pnl, conditioners, bins=3)
    for condition, group in table.groupby("condition"):
        assert group["share_of_total"].sum() == pytest.approx(1.0, abs=1e-6), condition


def test_fractionation_reports_the_columns_the_spec_names() -> None:
    pnl = _returns(200)
    table = fractionate(
        pnl, {"regime": pd.Series(np.arange(200) % 2, index=pnl.index)}, bins=2
    )
    assert list(table.columns) == [
        "condition",
        "bin",
        "n",
        "mean",
        "sharpe",
        "share_of_total",
    ]


def test_fractionation_counts_every_observation_exactly_once() -> None:
    pnl = _returns(300)
    conditioner = pd.Series(np.arange(300) % 5, index=pnl.index)
    table = fractionate(pnl, {"regime": conditioner}, bins=5)
    assert int(table["n"].sum()) == 300


def test_fractionation_skips_a_conditioner_that_is_entirely_missing() -> None:
    pnl = _returns(100)
    empty = pd.Series(np.nan, index=pnl.index)
    table = fractionate(pnl, {"regime": empty}, bins=3)
    assert table.empty


def test_fractionation_bins_accepts_a_per_condition_map() -> None:
    """A discrete regime code and a continuous utilisation series need different
    resolutions, so `bins` also takes a `{condition: n}` map, not just a single count."""
    pnl = _returns(400)
    rng = np.random.default_rng(9)
    conditioners = {
        "regime": pd.Series(rng.integers(0, 3, len(pnl)), index=pnl.index),
        "util": pd.Series(rng.random(len(pnl)), index=pnl.index),
    }
    table = fractionate(pnl, conditioners, bins={"regime": 3, "util": 4})
    assert table[table["condition"] == "regime"]["bin"].nunique() == 3
    assert table[table["condition"] == "util"]["bin"].nunique() == 4
    for condition, group in table.groupby("condition"):
        assert group["share_of_total"].sum() == pytest.approx(1.0, abs=1e-6), condition


# --- inventory predictability (Bouchouev) -----------------------------------------


def test_spreads_leading_inventories_is_detected() -> None:
    """Bouchouev's point: calendar spreads predict inventories more than inventories
    predict spreads. Built here so the spread genuinely leads, and the test asserts the
    verdict picks that direction."""
    n = 600
    rng = np.random.default_rng(3)
    idx = _index(n)
    s12 = pd.Series(rng.normal(0, 1, n), index=idx).cumsum()
    # Inventory follows last period's spread change, plus noise.
    inventory = pd.Series(
        np.r_[0.0, np.diff(s12.to_numpy())] * 3.0 + rng.normal(0, 0.1, n), index=idx
    ).cumsum()
    result = inventory_predictability_test(s12, inventory)
    assert result["spread_leads_inventory"] is True
    assert result["r2_spread_to_inventory"] > result["r2_inventory_to_spread"]


def test_inventory_predictability_reports_both_directions() -> None:
    n = 400
    rng = np.random.default_rng(4)
    idx = _index(n)
    s12 = pd.Series(rng.normal(0, 1, n), index=idx)
    inventory = pd.Series(rng.normal(0, 1, n), index=idx)
    result = inventory_predictability_test(s12, inventory)
    for key in (
        "r2_spread_to_inventory",
        "r2_inventory_to_spread",
        "t_spread_to_inventory",
        "t_inventory_to_spread",
        "n_obs",
        "spread_leads_inventory",
    ):
        assert key in result, key


def test_inventory_predictability_needs_enough_overlapping_history() -> None:
    idx = _index(5)
    tiny = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=idx)
    with pytest.raises(ValueError, match="observations"):
        inventory_predictability_test(tiny, tiny)


# --- spread P&L normalisation -----------------------------------------------------


def test_spread_to_return_is_stable_when_the_price_collapses() -> None:
    """Dividing a dollar spread change by the *spot* price explodes when that price nears
    zero. WTI settled at -$37.63 on 2020-04-20 and traded near $10 the next day, which
    inflated a calendar-spread strategy's annualised vol from ~12% to ~94% -- three days
    doing all of it. A trailing median notional is stable across the same episode.
    """
    idx = _index(400)
    spread = pd.Series(np.linspace(-1.0, 1.0, 400), index=idx)
    price = pd.Series(70.0, index=idx)
    price.iloc[300] = 0.01  # the collapse

    naive = spread.diff() / price
    stable = spread_to_return(spread, price, window=252)

    assert naive.abs().max() > 100 * stable.abs().max()
    assert np.isfinite(stable.dropna()).all()


def test_spread_to_return_uses_a_trailing_notional_not_the_future() -> None:
    idx = _index(400)
    spread = pd.Series(np.linspace(-1.0, 1.0, 400), index=idx)
    price = pd.Series(70.0, index=idx)
    full = spread_to_return(spread, price, window=252)
    short = spread_to_return(spread.iloc[:350], price.iloc[:350], window=252)
    np.testing.assert_allclose(
        full.iloc[:350].to_numpy(), short.to_numpy(), equal_nan=True, rtol=1e-12
    )


def test_spread_to_return_is_the_spread_change_over_the_notional() -> None:
    idx = _index(300)
    spread = pd.Series(np.arange(300, dtype=float), index=idx)
    price = pd.Series(50.0, index=idx)
    out = spread_to_return(spread, price, window=252)
    assert out.iloc[-1] == pytest.approx(1.0 / 50.0)
