"""DK1 imbalance settlement periods (ISPs) and their freeze deadlines.

An ISP is 15 minutes. Every call for it is due one minute before it starts,
so the database refuses anything frozen after that. A Copenhagen day has
96 ISPs, 92 on the spring clock change and 100 in October. Times are worked
out in UTC, because the repeated October hour makes local times ambiguous.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

COPENHAGEN = ZoneInfo("Europe/Copenhagen")
ISP = timedelta(minutes=15)
DUE_BEFORE = timedelta(minutes=1)
RELEASE_KIND = "dk1_isp"


@dataclass(frozen=True)
class Release:
    period_end: datetime  # the ISP's start, UTC; the release table's name for it
    scheduled_local: datetime  # Copenhagen wall clock, naive
    scheduled_at: datetime  # UTC
    basis: str = "isp"


def _local_midnight_utc(day):
    return datetime(day.year, day.month, day.day, tzinfo=COPENHAGEN).astimezone(UTC)


def isps(day):
    """The UTC start of every ISP in the Copenhagen day `day`."""
    start, end = _local_midnight_utc(day), _local_midnight_utc(day + timedelta(days=1))
    out = []
    while start < end:
        out.append(start)
        start += ISP
    return out


def isp_release(start):
    due = start - DUE_BEFORE
    local = due.astimezone(COPENHAGEN).replace(tzinfo=None)
    return Release(start, local, due)


def isp_releases(first_day, last_day):
    out, day = [], first_day
    while day <= last_day:
        out += [isp_release(s) for s in isps(day)]
        day += timedelta(days=1)
    return out


def today_copenhagen(now):
    return now.astimezone(COPENHAGEN).date()
