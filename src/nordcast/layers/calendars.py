"""Release-calendar constants and next-release lookups. Times are approximate ("~")
for OPEC MOMR and JODI, which publish on a date range/estimate rather than a fixed
schedule — see NOTES.md's data release calendar for the source list.

`roll_calendar`/`roll_window_flag` are this module's first real business-day arithmetic
(Spec 18 Session C) — plain Mon-Fri via numpy.busday_offset, the same convention
core/curve.py already established (confirmed with the user: no real CME/ICE holiday
calendar yet, since there's no real settlement data to need holiday-exact dates against).
Genuinely additive -- nothing here touches the RELEASES/next_release machinery above."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

import pandas as pd

_ET = ZoneInfo("America/New_York")
_CT = ZoneInfo("America/Chicago")
_CET = ZoneInfo("Europe/Berlin")
_UTC = ZoneInfo("UTC")


@dataclass(frozen=True)
class ReleaseSchedule:
    kind: Literal["weekly", "daily", "monthly"]
    tz: ZoneInfo
    hour: int
    minute: int = 0
    weekday: int | None = None  # Monday=0 .. Sunday=6, weekly only
    day_of_month: int | None = None  # monthly only


RELEASES: dict[str, ReleaseSchedule] = {
    "wpsr": ReleaseSchedule(kind="weekly", tz=_ET, weekday=2, hour=10, minute=30),
    "eia_gas_storage": ReleaseSchedule(
        kind="weekly", tz=_ET, weekday=3, hour=10, minute=30
    ),
    "agsi": ReleaseSchedule(kind="daily", tz=_CET, hour=19, minute=30),
    "baker_hughes": ReleaseSchedule(
        kind="weekly", tz=_CT, weekday=4, hour=12, minute=0
    ),
    "cftc_cot": ReleaseSchedule(kind="weekly", tz=_ET, weekday=4, hour=15, minute=30),
    "opec_momr": ReleaseSchedule(kind="monthly", tz=_UTC, day_of_month=12, hour=0),
    "jodi": ReleaseSchedule(kind="monthly", tz=_UTC, day_of_month=20, hour=0),
}


def _next_weekly(now_local: datetime, schedule: ReleaseSchedule) -> datetime:
    assert schedule.weekday is not None
    candidate = now_local.replace(
        hour=schedule.hour, minute=schedule.minute, second=0, microsecond=0
    )
    days_ahead = (schedule.weekday - now_local.weekday()) % 7
    candidate += timedelta(days=days_ahead)
    if candidate <= now_local:
        candidate += timedelta(days=7)
    return candidate


def _next_daily(now_local: datetime, schedule: ReleaseSchedule) -> datetime:
    candidate = now_local.replace(
        hour=schedule.hour, minute=schedule.minute, second=0, microsecond=0
    )
    if candidate <= now_local:
        candidate += timedelta(days=1)
    return candidate


def _next_monthly(now_local: datetime, schedule: ReleaseSchedule) -> datetime:
    assert schedule.day_of_month is not None
    candidate = now_local.replace(
        day=schedule.day_of_month,
        hour=schedule.hour,
        minute=schedule.minute,
        second=0,
        microsecond=0,
    )
    if candidate <= now_local:
        if candidate.month == 12:
            candidate = candidate.replace(year=candidate.year + 1, month=1)
        else:
            candidate = candidate.replace(month=candidate.month + 1)
    return candidate


def next_release(name: str, now: datetime) -> datetime:
    schedule = RELEASES[name]
    now_local = now.astimezone(schedule.tz)

    if schedule.kind == "weekly":
        return _next_weekly(now_local, schedule)
    if schedule.kind == "daily":
        return _next_daily(now_local, schedule)
    return _next_monthly(now_local, schedule)


# Index roll windows: (1-indexed first business day of the window, count of business days).
# GSCI rolls business days 5-9 of the month; BCOM rolls business days 6-10 -- both real,
# public index-methodology conventions, 0.2/day (5 equal daily tranches).
_ROLL_WINDOWS: dict[str, tuple[int, int]] = {"gsci": (5, 5), "bcom": (6, 5)}
_ROLL_FRACTION_PER_DAY = 0.2


def _month_business_days(year: int, month: int) -> pd.DatetimeIndex:
    start = pd.Timestamp(year=year, month=month, day=1)
    end = start + pd.offsets.MonthEnd(0)
    return pd.bdate_range(start, end)


def roll_calendar(year: int, index: str) -> pd.DataFrame:
    """One row per business day in that index's own roll window, every month of `year`.
    Columns: date, fraction (0.2, five equal tranches per month by construction --
    fractions per month always sum to 1.0). `index`: "gsci" | "bcom"."""
    if index not in _ROLL_WINDOWS:
        raise ValueError(f"index={index!r} not recognised -- expected 'gsci' or 'bcom'")
    first_bday, count = _ROLL_WINDOWS[index]

    rows = []
    for month in range(1, 13):
        bdays = _month_business_days(year, month)
        window = bdays[first_bday - 1 : first_bday - 1 + count]
        for d in window:
            rows.append({"date": d, "fraction": _ROLL_FRACTION_PER_DAY})
    return pd.DataFrame(rows, columns=["date", "fraction"])


def roll_window_flag(dates: pd.DatetimeIndex, year: int, index: str) -> pd.Series:
    """True for any `dates` entry that falls inside `index`'s own roll window, any month
    of `year`; False elsewhere (including dates outside `year` entirely)."""
    window_dates = set(roll_calendar(year, index)["date"])
    return pd.Series([pd.Timestamp(d) in window_dates for d in dates], index=dates)


def next_roll_window(index: str, now: date) -> date:
    """First date in `index`'s own roll_calendar that is >= `now` -- checks `now.year`
    first, then `now.year + 1` if every window in `now.year` has already passed (e.g. a
    December date past BCOM's own window). Real, live calendar arithmetic -- needs no lake
    data at all."""
    now_ts = pd.Timestamp(now)
    for year in (now.year, now.year + 1):
        cal = roll_calendar(year, index)
        upcoming = cal[cal["date"] >= now_ts]
        if not upcoming.empty:
            return pd.Timestamp(upcoming["date"].min()).date()
    raise AssertionError(f"no {index!r} roll window found within a year of {now}")
