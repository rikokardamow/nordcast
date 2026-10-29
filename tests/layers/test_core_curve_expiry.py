from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from nordcast.layers.curve import nymex_expiry, roll_dates_from_calendar

# --- CL: 3 business days before the 25th of the preceding month -------------------


def test_cl_december_2026_expires_on_the_published_date() -> None:
    """NYMEX WTI terminates 3 business days before the 25th of the month preceding
    delivery. For Dec-2026: 25 Nov 2026 is a Wednesday, so three business days earlier
    is Friday 20 Nov 2026 -- the real published expiry."""
    assert nymex_expiry("cl", 2026, 12) == date(2026, 11, 20)


def test_cl_expiry_steps_back_when_the_25th_is_a_weekend() -> None:
    """If the 25th is not a business day, the count starts from the business day before
    it. 25 Apr 2026 is a Saturday -> start from Fri 24 Apr, three business days back is
    Tue 21 Apr."""
    assert nymex_expiry("cl", 2026, 5) == date(2026, 4, 21)


def test_cl_expiry_rolls_january_back_into_the_previous_year() -> None:
    """Jan-2027 counts back from 25 Dec 2026, a Friday: 24th, 23rd, 22nd -> Tue 22 Dec.

    This is also the clearest example of the module's documented weekends-only
    approximation: 25 December is Christmas, so the exchange's own calendar would treat
    it as a holiday and the published date can differ by a day. Holiday-exact roll dates
    need a real trading calendar, which this project has deliberately not added.
    """
    assert nymex_expiry("cl", 2027, 1) == date(2026, 12, 22)


# --- products: last business day of the preceding month ---------------------------


def test_product_roots_expire_on_the_last_business_day_of_the_prior_month() -> None:
    """RBOB and heating oil terminate on the last business day of the month before
    delivery -- a different rule from crude, not the same one."""
    assert nymex_expiry("rb", 2026, 12) == date(2026, 11, 30)  # Mon 30 Nov 2026
    assert nymex_expiry("ho", 2026, 6) == date(2026, 5, 29)  # Fri 29 May 2026


def test_an_unknown_root_is_rejected_rather_than_guessed() -> None:
    with pytest.raises(ValueError, match="no expiry rule"):
        nymex_expiry("tfm", 2026, 12)


# --- roll dates over an index -----------------------------------------------------


def test_roll_dates_land_once_per_month() -> None:
    index = pd.bdate_range("2020-01-01", "2023-12-31")
    rolls = roll_dates_from_calendar("cl", index)
    per_year = rolls.groupby(rolls.index.year).sum()
    assert per_year.between(11, 13).all(), per_year.to_dict()


def test_roll_is_the_business_day_after_expiry() -> None:
    """EIA's "Contract 1" still shows the expiring contract on its last trading day; the
    rank moves to the next contract the following business day."""
    index = pd.bdate_range("2026-11-01", "2026-12-05")
    rolls = roll_dates_from_calendar("cl", index)
    assert rolls.loc[pd.Timestamp("2026-11-23")]  # Mon after Fri 20 Nov expiry
    assert not rolls.loc[pd.Timestamp("2026-11-20")]


def test_roll_dates_outside_the_index_are_ignored() -> None:
    index = pd.bdate_range("2026-11-24", "2026-11-30")
    assert not roll_dates_from_calendar("cl", index).any()
