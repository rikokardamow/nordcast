"""L1: what I'd have done with each frozen call (notes/later/risk-trading-layers.md).

A call becomes a position in [-1, 1], times the stated 10 MW (notes/limits.md):

- signal: the call's point (q50) divided by the rolling standard deviation of
  its own past calls. Not demeaned: the notes ask for "z-scored against its own
  recent distribution" *and* "direction = sign of the nowcast", and DK1's
  imbalance mean is negative (~-60 MW), so subtracting it would turn a call of
  -30 MW long. Scaling by the rolling sd keeps the sign and sizes the call
  against recent volatility. The convention, stated here, as the energy-analyst
  skill (local, not in git) asks; it has no imbalance-settlement conventions.
- sizing: `reaction` (layers.systematic), peaking at 1 for z = 1 and backing off
  further out.
- conviction filter: no position where the call's q10-q90 band includes zero.
- guardrail: capped at GUARDRAIL_CAP when the feed was stale at the freeze (the
  target's latest known ISP older than usual for the horizon).

Strategies follow layers.strategies' shape: a registry, `required_inputs`, and
`build_positions` that raises on a missing input rather than return a flat
series. A missing call is NaN, never zero (the skill: "missing data must be
NaN, not 0").
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from nordcast.layers.systematic import GUARDRAIL_CAP, position

SIZE_MW = 10.0
SD_WINDOW = 7 * 96  # a week of ISPs
USUAL_STEPS = {
    15: 4,
    30: 5,
    60: 7,
}  # latest known ISP to target, in ISPs (training rows)


class MissingInput(Exception):
    pass


@dataclass(frozen=True)
class Strategy:
    name: str
    required_inputs: tuple[str, ...]  # columns of the calls frame
    note: str = ""


REGISTRY = {
    "forecast": Strategy(
        "forecast", ("point", "q10", "q90", "steps_ahead"),
        "the record's call: point scaled by its rolling sd, reaction-sized, "
        "conviction-filtered, stale-feed capped",
    ),
    "persistence": Strategy(
        "persistence", ("pers_point", "pers_q10", "pers_q90", "steps_ahead"),
        "the control: the same construction on persistence's call",
    ),
}  # fmt: skip


def signal(point, window=SD_WINDOW):
    """point / rolling sd of past points (the call at t is known at its freeze)."""
    sd = point.rolling(window, min_periods=window // 2).std()
    return point / sd


def raw_position(point, q10, q90, steps, horizon, window=SD_WINDOW):
    """Position in [-1, 1] before sizing to MW."""
    pos = position(signal(point, window), sizing="reaction")
    pos = pos.where(~((q10 <= 0) & (q90 >= 0)), 0.0)  # conviction filter
    stale = steps > USUAL_STEPS[horizon]
    pos = pos.mask(stale, pos.clip(-GUARDRAIL_CAP, GUARDRAIL_CAP))
    return pos.where(point.notna())  # no call, no position: NaN, never 0


def build_positions(name, calls, horizon, window=SD_WINDOW):
    """MW positions for one strategy at one horizon, indexed like `calls`.

    Raises MissingInput when a required column is absent or entirely empty."""
    strategy = REGISTRY[name]
    absent = [c for c in strategy.required_inputs if c not in calls.columns]
    empty = [
        c for c in strategy.required_inputs if c in calls and calls[c].isna().all()
    ]
    if absent or empty:
        raise MissingInput(f"{name}: absent {absent}, empty {empty}")
    point, q10, q90, steps = (calls[c] for c in strategy.required_inputs)
    pos = raw_position(point, q10, q90, steps, horizon, window)
    out = pos * SIZE_MW
    if (out.abs() > SIZE_MW + 1e-9).any():
        raise AssertionError("a position above the 10 MW limit")  # notes/limits.md
    return out.rename(f"{name}_mw")


def called_direction(pos):
    """'up' for a long, 'down' for a short, 'none' when flat; NaN stays NaN."""
    out = pd.Series(
        np.select([pos > 0, pos < 0], ["up", "down"], "none"), index=pos.index
    )
    return out.where(pos.notna())
