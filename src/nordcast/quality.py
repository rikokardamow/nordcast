"""Checks on a pull before anything is scored.

Blocking: no rows, null values, or the week we expected isn't there yet.
Warning only: a weekly change more than 3 standard deviations from the
last year's changes. It's scored, but flagged.
"""

import statistics
from dataclasses import dataclass, field


@dataclass
class Gate:
    blocking: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def ok(self):
        return not self.blocking


def check_pull(rows, expected_week):
    gate = Gate()
    if not rows:
        gate.blocking.append("no rows")
        return gate
    nulls = sum(1 for r in rows if r.get("value") in (None, ""))
    if nulls:
        gate.blocking.append(f"{nulls} null values")
    latest = max(r["period"] for r in rows)
    if latest < expected_week.isoformat():
        gate.blocking.append(
            f"stale: latest week is {latest}, expected {expected_week}"
        )
    return gate


def is_outlier(change, past_changes, sigmas=3):
    if len(past_changes) < 2:
        return False
    mean = statistics.mean(past_changes)
    sd = statistics.stdev(past_changes)
    return sd > 0 and abs(change - mean) > sigmas * sd
