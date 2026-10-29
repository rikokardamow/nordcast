from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from nordcast import pnl

T0 = datetime(2026, 7, 1, 22, tzinfo=UTC)  # 00:00 Copenhagen, 2 Jul


def calls(n=96 * 3, seed=3):
    rng = np.random.default_rng(seed)
    idx = pd.DatetimeIndex([T0 + timedelta(minutes=15 * k) for k in range(n)])
    da = rng.normal(80, 20, n)
    return pd.DataFrame(
        {"imb_price": da + rng.normal(0, 60, n), "da_price_target": da}, index=idx
    )


def test_a_constant_long_reproduces_holding_every_isp_at_zero_cost():
    """backtest()'s first acceptance guard, in nordcast units: +1 MW in every ISP
    earns exactly the sum of 0.25 x (imbalance - day-ahead)."""
    c = calls()
    frame, _ = pnl.run(pd.Series(1.0, index=c.index), c, slippage=0.0, limit=np.inf)
    assert frame.net.sum() == pytest.approx(pnl.earned_per_mw(c).sum())


def test_shifting_the_prices_one_step_changes_the_pnl():
    """backtest()'s second guard: a position earns its own ISP, not the next."""
    c = calls()
    pos = pd.Series(np.sign(c.imb_price - c.da_price_target) * 10, index=c.index)
    own, _ = pnl.run(pos, c, slippage=0.0, limit=np.inf)
    moved = c.assign(imb_price=c.imb_price.shift(1))
    shifted, _ = pnl.run(pos, moved, slippage=0.0, limit=np.inf)
    assert own.net.sum() > 0 and not np.isclose(own.net.sum(), shifted.net.sum())


def test_a_position_earns_its_own_isp():
    c = calls(n=8)
    pos = pd.Series(0.0, index=c.index)
    pos.iloc[3] = 10.0
    frame, _ = pnl.run(pos, c, slippage=0.0, limit=np.inf)
    expect = 10 * 0.25 * (c.imb_price.iloc[3] - c.da_price_target.iloc[3])
    assert frame.net.iloc[3] == pytest.approx(expect)
    assert (frame.net.drop(c.index[3]) == 0).all()


def test_slippage_is_charged_on_every_held_isp():
    c = calls(n=4)
    frame, _ = pnl.run(pd.Series(-10.0, index=c.index), c, slippage=2.0, limit=np.inf)
    assert (frame.cost == 10 * 0.25 * 2.0).all()


def test_the_daily_loss_limit_flattens_the_rest_of_the_day():
    c = calls(n=96 * 2)
    c["imb_price"] = (
        c.da_price_target - 1000.0
    )  # every long loses 2,500 EUR an ISP at 10 MW
    frame, breaches = pnl.run(
        pd.Series(10.0, index=c.index), c, slippage=0.0, limit=5_000
    )
    day1 = frame.iloc[:96]
    assert (day1.pos_mw.iloc[:2] == 10).all() and (day1.pos_mw.iloc[2:] == 0).all()
    assert day1.net.sum() == pytest.approx(-5_000)
    assert len(breaches) == 2  # the next day starts fresh, and breaches again
    assert (frame.iloc[96:98].pos_mw == 10).all()


def test_an_unpriced_isp_earns_nothing_and_is_counted():
    c = calls(n=8)
    c.iloc[5, c.columns.get_loc("imb_price")] = np.nan
    frame, breaches = pnl.run(pd.Series(10.0, index=c.index), c)
    assert np.isnan(frame.net.iloc[5])
    assert pnl.summary(frame, breaches)["unpriced_positioned_isps"] == 1
