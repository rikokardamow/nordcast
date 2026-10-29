from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nordcast.layers.curve import (
    back_adjust_from_ranks,
    roll_dates_from_calendar,
    roll_flags_from_ranks,
)


def _rank_panel() -> tuple[pd.DataFrame, int]:
    """A rank panel spanning one real CL roll, built from two contract paths.

    The roll date comes from the exchange's own expiry rule, not from the price pattern,
    so the fixture is constructed around whatever `roll_dates_from_calendar` says. Each
    contract drifts +1/day and the next one trades 2.0 higher (contango), so the raw f01
    series shows a -2.0 step at the roll that neither contract actually experienced --
    exactly the artefact back-adjustment removes.
    """
    index = pd.bdate_range("2026-01-05", "2026-02-06")
    rolls = roll_dates_from_calendar("cl", index)
    position = int(np.flatnonzero(rolls.to_numpy())[0])

    front = np.arange(len(index), dtype=float) + 100.0  # the contract that is f01 first
    second = front + 2.0  # the contract that takes over at the roll
    f01 = np.where(np.arange(len(index)) < position, front, second)
    f02 = np.where(np.arange(len(index)) < position, second, second + 2.0)
    panel = pd.DataFrame({"f01": f01, "f02": f02}, index=index)
    return panel, position


# --- roll detection ---------------------------------------------------------------


def test_roll_lands_on_the_calendar_roll_date() -> None:
    """The flag comes from the published expiry rule, so it must fall exactly where
    roll_dates_from_calendar puts it -- and nowhere else in the month."""
    panel, position = _rank_panel()
    flags = roll_flags_from_ranks(panel, "cl")
    assert flags.iloc[position]
    assert int(flags.sum()) == 1


def test_a_window_containing_no_roll_date_flags_nothing() -> None:
    """Late November sits after the CL roll, so a short window there has none."""
    index = pd.bdate_range("2026-11-24", "2026-11-30")
    panel = pd.DataFrame(
        {
            "f01": np.linspace(100, 105, len(index)),
            "f02": np.linspace(102, 107, len(index)),
        },
        index=index,
    )
    assert not roll_flags_from_ranks(panel, "cl").any()


# --- back adjustment --------------------------------------------------------------


def test_back_adjustment_leaves_the_most_recent_segment_untouched() -> None:
    """Ratio adjustment is built backwards from the latest segment, whose factor is 1, so
    today's adjusted price is today's real price."""
    panel, _ = _rank_panel()
    adjusted = back_adjust_from_ranks(panel, "cl")
    assert adjusted.iloc[-1] == pytest.approx(panel["f01"].iloc[-1])


def test_the_roll_day_return_is_the_new_contracts_own_return_not_a_jump() -> None:
    """The whole point: crossing the roll, the adjusted return must be the incoming
    contract's own one-day return, not the raw cross-contract step."""
    panel, position = _rank_panel()
    adjusted = back_adjust_from_ranks(panel, "cl")
    realised = adjusted.iloc[position] / adjusted.iloc[position - 1]
    # The incoming contract was f02 the day before and f01 on the roll day.
    expected = panel["f01"].iloc[position] / panel["f02"].iloc[position - 1]
    assert realised == pytest.approx(expected, abs=1e-12)
    raw_jump = panel["f01"].iloc[position] / panel["f01"].iloc[position - 1]
    assert realised != pytest.approx(raw_jump)


def test_back_adjustment_removes_the_artificial_roll_step() -> None:
    """In contango the incoming contract trades higher, so raw f01 leaps the width of the
    spread on top of the real move (+3.0 here, of which only +1.0 is real). The adjusted
    series must show only the real move."""
    panel, position = _rank_panel()
    raw_step = panel["f01"].iloc[position] - panel["f01"].iloc[position - 1]
    adjusted = back_adjust_from_ranks(panel, "cl")
    adj_step = adjusted.iloc[position] - adjusted.iloc[position - 1]
    assert raw_step == pytest.approx(3.0)  # +1 real move, +2 spread artefact
    assert adj_step == pytest.approx(1.0, abs=0.05)  # the real move alone


def test_a_panel_with_no_rolls_is_returned_unchanged() -> None:
    index = pd.bdate_range("2026-11-24", "2026-11-30")
    f01 = pd.Series(np.linspace(100, 105, len(index)), index=index)
    panel = pd.DataFrame({"f01": f01, "f02": f01 + 2.0})
    pd.testing.assert_series_equal(
        back_adjust_from_ranks(panel, "cl"), f01, check_names=False
    )


def test_back_adjustment_never_uses_a_future_observation() -> None:
    """Truncating the panel rescales the level (the anchor segment changes) but must not
    change any *return* before the truncation point."""
    panel, position = _rank_panel()
    full = back_adjust_from_ranks(panel, "cl")
    cut = position + 3
    short = back_adjust_from_ranks(panel.iloc[:cut], "cl")
    np.testing.assert_allclose(
        full.pct_change().iloc[1:cut].to_numpy(),
        short.pct_change().iloc[1:cut].to_numpy(),
        rtol=1e-12,
    )


def test_adjusted_series_is_strictly_positive_for_positive_prices() -> None:
    panel, _ = _rank_panel()
    assert (back_adjust_from_ranks(panel, "cl") > 0).all()
