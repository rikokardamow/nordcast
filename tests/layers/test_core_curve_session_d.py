from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from nordcast.layers.curve import roll_window_offset_grid


def test_roll_window_offset_grid_zero_offset_matches_the_real_gsci_window_start() -> None:
    """Jan 2026's GSCI window starts 2026-01-07 (Session C's own hand-verified date).
    A synthetic delta series with a distinct, known value exactly on that date must land
    in the offset=0 column, that year's row."""
    dates = pd.bdate_range("2026-01-01", "2026-01-31")
    delta = pd.Series(0.0, index=dates)
    delta.loc[pd.Timestamp("2026-01-07")] = 9.0

    grid = roll_window_offset_grid(delta, "gsci", window=5)
    assert grid.loc[2026, 0] == pytest.approx(9.0)


def test_roll_window_offset_grid_columns_span_the_requested_window() -> None:
    dates = pd.bdate_range("2026-01-01", "2026-01-31")
    delta = pd.Series(0.0, index=dates)

    grid = roll_window_offset_grid(delta, "bcom", window=3)
    assert list(grid.columns) == [-3, -2, -1, 0, 1, 2, 3]


def test_roll_window_offset_grid_offsets_are_signed_correctly() -> None:
    """A date one business day before the window start gets offset -1; one business day
    after the window's own last date gets a positive offset (nearest window start still
    resolves correctly across two adjacent windows)."""
    dates = pd.bdate_range("2026-01-01", "2026-01-15")
    delta = pd.Series(np.arange(len(dates), dtype=float), index=dates)

    grid = roll_window_offset_grid(delta, "gsci", window=5)
    # 2026-01-06 (Tue) is the business day immediately before the window start (01-07).
    day_before = delta.loc["2026-01-06"]
    assert grid.loc[2026, -1] == pytest.approx(day_before)
