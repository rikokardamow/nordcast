from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

from nordcast.layers.systematic import (
    apply_guardrails,
    blend,
    carry,
    carry_pct,
    convexity_signal,
    momentum_ma,
    momentum_on_carry,
    momentum_ret,
    position,
    reaction,
    reaction_piecewise,
    value,
    vol_target,
    zscore,
)


def _index(n: int) -> pd.DatetimeIndex:
    return pd.bdate_range("2020-01-01", periods=n)


def _backwardated(n: int = 300) -> pd.DataFrame:
    """Front above deferred at every rank -- an unambiguously backwardated curve."""
    idx = _index(n)
    return pd.DataFrame({"f01": 80.0, "f02": 79.0, "f03": 78.5, "f04": 78.2}, index=idx)


def _contango(n: int = 300) -> pd.DataFrame:
    idx = _index(n)
    return pd.DataFrame({"f01": 78.0, "f02": 79.0, "f03": 80.0, "f04": 81.0}, index=idx)


# --- reaction function (the spec's own acceptance values) --------------------------


def test_reaction_is_one_at_z_equals_one() -> None:
    """R(z) = z * exp(0.5 * (1 - z^2)) peaks at z=1 with R(1)=1."""
    assert reaction(pd.Series([1.0])).iloc[0] == pytest.approx(1.0)


def test_reaction_is_zero_at_zero() -> None:
    assert reaction(pd.Series([0.0])).iloc[0] == pytest.approx(0.0)


def test_reaction_at_two_matches_the_specs_published_value() -> None:
    """R(2) = 2 * e^-1.5 ~= 0.4463 -- the spec's own stated constant."""
    assert reaction(pd.Series([2.0])).iloc[0] == pytest.approx(
        2 * np.exp(-1.5), abs=1e-9
    )
    assert reaction(pd.Series([2.0])).iloc[0] == pytest.approx(0.446, abs=0.001)


def test_reaction_rises_on_zero_to_one_and_falls_on_one_to_three() -> None:
    """The whole point of a reaction function: conviction grows to a point, then a more
    extreme signal is treated as a regime the model does not understand, not a bigger bet.
    """
    up = reaction(pd.Series(np.linspace(0, 1, 50)))
    down = reaction(pd.Series(np.linspace(1, 3, 50)))
    assert (up.diff().dropna() > 0).all()
    assert (down.diff().dropna() < 0).all()


def test_reaction_is_odd_symmetric() -> None:
    z = pd.Series([-2.5, -1.0, -0.3, 0.3, 1.0, 2.5])
    assert reaction(z).to_numpy() == pytest.approx(-reaction(-z).to_numpy())


def test_reaction_clips_its_input_to_plus_minus_three() -> None:
    """Beyond |z|=3 the function would keep shrinking towards zero; the spec clips the
    input so an extreme reading holds the tail value rather than vanishing."""
    assert reaction(pd.Series([5.0])).iloc[0] == pytest.approx(
        reaction(pd.Series([3.0])).iloc[0]
    )
    assert reaction(pd.Series([-5.0])).iloc[0] == pytest.approx(
        reaction(pd.Series([-3.0])).iloc[0]
    )


def test_reaction_piecewise_plateaus_then_cuts_off() -> None:
    z = pd.Series([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
    out = reaction_piecewise(z, plateau=1.0, cutoff=2.5)
    assert out.iloc[0] == pytest.approx(0.0)
    assert out.iloc[2] == pytest.approx(1.0)  # at the plateau
    assert out.iloc[3] == pytest.approx(1.0)  # still on it
    assert out.iloc[6] == pytest.approx(0.0)  # past the cutoff


# --- carry ------------------------------------------------------------------------


def test_carry_is_positive_on_a_backwardated_curve() -> None:
    """The spec's own acceptance test: carry sign is +1 when the front is above the
    deferred."""
    assert (carry(_backwardated(), near=1, far=3) > 0).all()
    assert np.sign(carry(_backwardated(), near=1, far=3).iloc[-1]) == 1


def test_carry_is_negative_in_contango() -> None:
    assert (carry(_contango(), near=1, far=3) < 0).all()


def test_carry_is_the_plain_price_difference() -> None:
    panel = _backwardated()
    expected = panel["f01"] - panel["f03"]
    pd.testing.assert_series_equal(carry(panel, 1, 3), expected, check_names=False)


def test_carry_pct_annualises_by_the_months_between_the_legs() -> None:
    """A 1.5 backwardation on a 78.5 deferred leg, two months apart, is a 6x annualised
    rate, not the raw ratio."""
    panel = _backwardated()
    raw = (80.0 - 78.5) / 78.5
    assert carry_pct(panel, 1, 3).iloc[-1] == pytest.approx(raw * 6.0)


def test_carry_rejects_a_rank_the_panel_does_not_have() -> None:
    """EIA publishes ranks 1-4 only, so the spec's own far=13 default cannot be served
    from that source -- fail loudly rather than return silence."""
    with pytest.raises(KeyError, match="f13"):
        carry(_backwardated(), near=1, far=13)


# --- momentum, value, convexity ---------------------------------------------------


def test_momentum_ma_is_price_less_its_moving_average() -> None:
    prices = pd.Series(np.linspace(50, 150, 300), index=_index(300))
    out = momentum_ma(prices, n=100)
    assert out.iloc[:99].isna().all()
    assert (out.dropna() > 0).all()  # a rising series sits above its own MA


def test_momentum_ret_is_the_n_day_return() -> None:
    prices = pd.Series(np.linspace(100, 200, 300), index=_index(300))
    out = momentum_ret(prices, n=252)
    assert out.iloc[:252].isna().all()
    assert out.dropna().gt(0).all()


def test_value_is_contrarian_to_the_long_run_mean() -> None:
    """Value buys what is cheap: the signal must be positive when price sits below its
    own long-run average, which is the opposite sign to momentum."""
    prices = pd.Series(np.linspace(150, 50, 1400), index=_index(1400))
    out = value(prices, n=1260).dropna()
    assert (
        out > 0
    ).all()  # falling series ends below its mean -> positive value signal


def test_convexity_signal_is_the_sign_of_cv123() -> None:
    signal = convexity_signal(_backwardated())
    assert set(np.unique(signal.dropna())).issubset({-1.0, 0.0, 1.0})


def test_momentum_on_carry_measures_the_change_in_carry() -> None:
    carry_series = pd.Series(np.linspace(-2, 2, 200), index=_index(200))
    out = momentum_on_carry(carry_series, n=60)
    assert (out.dropna() > 0).all()  # steadily improving carry


# --- z-score and vol targeting ----------------------------------------------------


def test_zscore_is_rolling_not_full_sample() -> None:
    """A full-sample z uses the future. core.macro.zscore is deliberately the full-sample
    one for a different purpose -- this is not that function."""
    x = pd.Series(np.arange(300, dtype=float), index=_index(300))
    out = zscore(x, window=252)
    assert out.iloc[:251].isna().all()
    assert out.iloc[251:].notna().any()


def test_zscore_never_uses_a_future_observation() -> None:
    x = pd.Series(np.random.default_rng(0).normal(size=400), index=_index(400))
    full = zscore(x, window=100)
    short = zscore(x.iloc[:300], window=100)
    np.testing.assert_allclose(
        full.iloc[:300].to_numpy(), short.to_numpy(), equal_nan=True, rtol=1e-12
    )


def test_vol_target_scales_down_when_realised_vol_exceeds_the_target() -> None:
    rng = np.random.default_rng(1)
    high = pd.Series(rng.normal(0, 0.04, 300), index=_index(300))  # ~63% annualised
    scale = vol_target(high, target_ann=0.10, window=63).dropna()
    assert (scale < 1.0).all()


def test_vol_target_scales_up_when_realised_vol_is_below_the_target() -> None:
    rng = np.random.default_rng(2)
    low = pd.Series(rng.normal(0, 0.001, 300), index=_index(300))  # ~1.6% annualised
    assert (vol_target(low, target_ann=0.10, window=63).dropna() > 1.0).all()


# --- blending and position sizing -------------------------------------------------


def test_blend_is_the_weighted_sum_of_its_signals() -> None:
    a = pd.Series([1.0, 2.0], index=_index(2))
    b = pd.Series([3.0, 4.0], index=_index(2))
    out = blend({"a": a, "b": b}, {"a": 0.5, "b": 0.5})
    assert out.tolist() == pytest.approx([2.0, 3.0])


def test_blend_rejects_a_weight_with_no_matching_signal() -> None:
    a = pd.Series([1.0], index=_index(1))
    with pytest.raises(KeyError):
        blend({"a": a}, {"a": 0.5, "missing": 0.5})


def test_position_is_bounded_to_plus_minus_one() -> None:
    z = pd.Series(np.linspace(-6, 6, 200), index=_index(200))
    for sizing in ("reaction", "piecewise", "sign", "linear"):
        out = position(z, sizing=sizing)
        assert out.between(-1.0, 1.0).all(), sizing


def test_position_rejects_an_unknown_sizing_rule() -> None:
    with pytest.raises(ValueError, match="sizing"):
        position(pd.Series([1.0]), sizing="nonsense")


# --- guardrails -------------------------------------------------------------------


def test_full_tanks_cap_short_spread_positions() -> None:
    """Cushing utilisation in the top decile already implies contango, so the consensus
    short-spread trade is capped at 25% rather than run at full size."""
    pos = pd.Series([-1.0, -1.0], index=_index(2))
    util = pd.Series([9.0, 5.0], index=_index(2))
    cot = pd.Series([0.5, 0.5], index=_index(2))
    out = apply_guardrails(pos, util, cot)
    assert out.iloc[0] == pytest.approx(-0.25)  # capped
    assert out.iloc[1] == pytest.approx(-1.0)  # untouched


def test_empty_tanks_cap_long_positions() -> None:
    pos = pd.Series([1.0, 1.0], index=_index(2))
    util = pd.Series([2.0, 5.0], index=_index(2))
    cot = pd.Series([0.5, 0.5], index=_index(2))
    out = apply_guardrails(pos, util, cot)
    assert out.iloc[0] == pytest.approx(0.25)
    assert out.iloc[1] == pytest.approx(1.0)


def test_a_crowded_long_is_halved() -> None:
    pos = pd.Series([1.0], index=_index(1))
    util = pd.Series([5.0], index=_index(1))
    out = apply_guardrails(pos, util, pd.Series([0.97], index=_index(1)))
    assert out.iloc[0] == pytest.approx(0.5)


def test_a_crowded_short_is_halved() -> None:
    pos = pd.Series([-1.0], index=_index(1))
    util = pd.Series([5.0], index=_index(1))
    out = apply_guardrails(pos, util, pd.Series([0.02], index=_index(1)))
    assert out.iloc[0] == pytest.approx(-0.5)


def test_a_crowded_long_does_not_penalise_a_short() -> None:
    """The crowding rule is directional -- an extreme managed-money long says nothing
    about the risk of being short."""
    pos = pd.Series([-1.0], index=_index(1))
    util = pd.Series([5.0], index=_index(1))
    out = apply_guardrails(pos, util, pd.Series([0.97], index=_index(1)))
    assert out.iloc[0] == pytest.approx(-1.0)


def test_guardrails_compose_the_tank_cap_and_the_crowding_halving() -> None:
    """Both conditions firing must apply both, not whichever came last."""
    pos = pd.Series([-1.0], index=_index(1))
    util = pd.Series([9.0], index=_index(1))
    out = apply_guardrails(pos, util, pd.Series([0.02], index=_index(1)))
    assert out.iloc[0] == pytest.approx(-0.125)  # -1 -> cap -0.25 -> halve


def test_guardrails_leave_positions_alone_when_conditioners_are_missing() -> None:
    """A NaN utilisation decile or COT percentile must not silently flatten a position."""
    pos = pd.Series([1.0, -1.0], index=_index(2))
    nan = pd.Series([np.nan, np.nan], index=_index(2))
    pd.testing.assert_series_equal(
        apply_guardrails(pos, nan, nan), pos, check_names=False
    )


# --- negative prices are real (2020-04-20) ----------------------------------------


def test_log_signals_are_undefined_not_warning_on_a_negative_price() -> None:
    """WTI settled at -$37.63 on 2020-04-20 and the lake holds that real print. Every
    log-based signal is genuinely undefined there, so it must return NaN cleanly rather
    than emit a RuntimeWarning and propagate a silent NaN.
    """
    prices = pd.Series([50.0, 40.0, -37.63, 20.0, 30.0], index=_index(5))
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any RuntimeWarning fails this test
        out = momentum_ret(prices, n=1)
        val = value(prices, n=2)
    assert np.isnan(out.iloc[2])
    assert np.isnan(val.iloc[2])


def test_a_negative_price_does_not_poison_later_observations() -> None:
    """The NaN must be confined to the days whose own window touches the negative print,
    not carried forward for the rest of the series."""
    prices = pd.Series([50.0, -10.0, 30.0, 31.0, 32.0, 33.0], index=_index(6))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = momentum_ret(prices, n=1)
    assert out.iloc[-1] == pytest.approx(np.log(33.0) - np.log(32.0))
