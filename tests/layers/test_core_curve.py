from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nordcast.layers.curve import (
    convexity,
    curve_regime,
    dec_dec,
    nearby_panel,
    transition_matrix,
)


def _three_contract_setup() -> tuple[pd.Series, pd.DatetimeIndex, pd.DataFrame]:
    expiries = pd.Series(
        {
            "f26": pd.Timestamp("2026-01-30"),
            "g26": pd.Timestamp("2026-02-27"),
            "h26": pd.Timestamp("2026-03-31"),
        }
    )
    dates = pd.bdate_range("2026-01-01", "2026-04-10")
    panel = pd.DataFrame({"f26": 50.0, "g26": 51.0, "h26": 52.0}, index=dates)
    return expiries, dates, panel


def test_roll_happens_on_the_exact_business_day_before_expiry() -> None:
    expiries, dates, panel = _three_contract_setup()
    _, _, roll_dates = nearby_panel(panel, expiries, roll_days_before_expiry=5)

    roll_date_f26 = pd.Timestamp(
        np.busday_offset(expiries["f26"].date(), -5, roll="backward")
    )
    loc = dates.get_loc(roll_date_f26)

    assert roll_dates.iloc[loc - 1] == "f26"  # day before the roll: still front
    assert roll_dates.iloc[loc] == "g26"  # roll day itself: already rolled


def test_contract_retires_from_every_rank_once_rolled_past() -> None:
    expiries, dates, panel = _three_contract_setup()
    _, unadj, roll_dates = nearby_panel(panel, expiries, roll_days_before_expiry=5)

    roll_date_f26 = pd.Timestamp(
        np.busday_offset(expiries["f26"].date(), -5, roll="backward")
    )
    loc = dates.get_loc(roll_date_f26)
    row = unadj.iloc[loc]

    assert row["f01"] == pytest.approx(51.0)  # g26, not f26
    assert row["f02"] == pytest.approx(52.0)  # h26
    assert roll_dates.iloc[loc] != "f26"  # f26 never reappears at any rank once retired


def test_zero_return_on_roll_day() -> None:
    """The new front contract's own price is held flat across the roll boundary -- a
    correctly ratio-adjusted series must show exactly 0.0 return on the roll day, since
    the adjusted return crossing a roll equals the new contract's own real return, never
    an artificial cross-contract jump."""
    expiries = pd.Series(
        {"f26": pd.Timestamp("2026-01-30"), "g26": pd.Timestamp("2026-02-27")}
    )
    dates = pd.bdate_range("2026-01-01", "2026-02-28")
    f26_prices = pd.Series(np.linspace(50.0, 55.0, len(dates)), index=dates)
    g26_prices = pd.Series(51.0, index=dates)  # flat
    panel = pd.DataFrame({"f26": f26_prices, "g26": g26_prices})

    adjusted, _, _ = nearby_panel(panel, expiries, roll_days_before_expiry=5)

    roll_date = pd.Timestamp(
        np.busday_offset(expiries["f26"].date(), -5, roll="backward")
    )
    loc = dates.get_loc(roll_date)

    ret = adjusted["f01"].pct_change().iloc[loc]
    assert ret == pytest.approx(0.0, abs=1e-9)


def test_dec_dec_reads_december_contracts_directly_off_contract_codes() -> None:
    dates = pd.bdate_range("2026-01-01", periods=3)
    panel = pd.DataFrame(
        {
            "z25": [80.0, 80.5, 81.0],
            "z26": [75.0, 75.2, 75.5],
            "f26": [70.0, 70.1, 70.2],  # not December -- must be ignored
        },
        index=dates,
    )

    result = dec_dec(panel)

    assert list(result.columns) == ["dec_dec_2025_2026"]
    pd.testing.assert_series_equal(
        result["dec_dec_2025_2026"], panel["z25"] - panel["z26"], check_names=False
    )


def test_convexity_matches_hand_computed_values() -> None:
    assert convexity(pd.DataFrame({"f01": [80.0], "f02": [79.0], "f03": [78.5]})).iloc[
        0
    ] == pytest.approx(0.5)
    assert convexity(pd.DataFrame({"f01": [80.0], "f02": [79.0], "f03": [77.0]})).iloc[
        0
    ] == pytest.approx(-1.0)


@pytest.mark.parametrize(
    ("f01", "f02", "f03", "expected_state"),
    [
        (80.0, 79.0, 78.5, "convex_backwardation"),  # s12=1>0, cv=0.5>0
        (80.0, 81.0, 81.5, "concave_contango"),  # s12=-1<0, cv=-0.5<=0
        (80.0, 81.0, 82.5, "convex_contango"),  # s12=-1<0, cv=0.5>0
        (80.0, 80.0, 79.0, "flat"),  # s12==0, no branch matches
    ],
)
def test_curve_regime_classifies_the_spec_worked_examples(
    f01: float, f02: float, f03: float, expected_state: str
) -> None:
    # A single-row unadj has no f12 (s1_12 is NaN, so super_contango can never fire) and
    # far fewer rows than `lookback` (slope_pct is NaN, so super_backwardation can never
    # fire either) -- exactly what isolates the four remaining/flat states for this test.
    unadj = pd.DataFrame({"f01": [f01], "f02": [f02], "f03": [f03]})
    result = curve_regime(unadj)
    assert result["state"].iloc[0] == expected_state


def test_transition_matrix_rows_sum_to_one() -> None:
    states = pd.Series(
        ["convex_contango", "convex_contango", "concave_contango", "convex_contango"]
    )
    matrix = transition_matrix(states)
    row_sums = matrix.sum(axis=1)
    assert row_sums.loc["convex_contango"] == pytest.approx(1.0)
    assert row_sums.loc["concave_contango"] == pytest.approx(1.0)


def test_transition_matrix_all_nan_row_for_a_state_with_no_outgoing_transition() -> (
    None
):
    # "flat" appears once, at the very end -- no outgoing transition was ever observed.
    states = pd.Series(
        ["convex_contango", "concave_contango", "convex_contango", "flat"]
    )
    matrix = transition_matrix(states)
    assert matrix.loc["flat"].isna().all()


def test_curve_regime_has_no_look_ahead() -> None:
    """curve_regime computed through day t must classify day t identically whether the
    input panel stops at t or continues 20 days further -- this only holds if slope_pct's
    rolling window looks backward only."""
    dates = pd.bdate_range("2026-01-01", periods=40)
    rng = np.random.default_rng(42)
    f01 = pd.Series(80 + rng.normal(0, 1, len(dates)).cumsum(), index=dates)
    f02 = f01 - 1.0
    f03 = f02 - 0.5
    unadj = pd.DataFrame({"f01": f01, "f02": f02, "f03": f03})

    t = 20
    truncated = curve_regime(unadj.iloc[: t + 1], lookback=5)
    full = curve_regime(unadj, lookback=5)

    assert truncated["state"].iloc[t] == full["state"].iloc[t]
    assert truncated["slope_pct"].iloc[t] == pytest.approx(full["slope_pct"].iloc[t])
