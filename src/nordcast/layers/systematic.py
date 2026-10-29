"""Systematic strategy signals and position sizing (Spec 21, after Bouchouev,
*Virtual Barrels* Ch. 5-6).

Pure maths only -- never touches DuckDB (root NOTES.md rule 2). `pipelines/derived/
systematic.py` reads the lake, calls these, and writes `derived.pos.<strategy>.<root>`.

Vectorised pandas throughout, no per-date loops (the spec's own Session A instruction).
Spreads and convexity are imported from `core/curve.py` rather than recomputed.

**Rank availability, checked live before writing this.** The spec's headline carry is
C(1,13) -- rank 1 against rank 13. The lake's only futures source (EIA) publishes ranks
**1-4 only**, so `carry`'s own `far=13` default cannot be served and Bouchouev's published
C(1,13) anchor (20.3% annualised, Sharpe 0.53) is not reproducible here. The default is
kept to match the spec; `carry` raises a clear KeyError rather than returning silence when
the rank is absent.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from nordcast.layers.curve import convexity

REACTION_CLIP = 3.0
"""The spec clips the reaction function's input to [-3, 3]."""

TRADING_DAYS = 252
MONTHS_PER_YEAR = 12

FULL_TANKS_DECILE = 9
"""Cushing utilisation at or above this decile already implies contango."""

EMPTY_TANKS_DECILE = 2
CROWDED_LONG = 0.95
CROWDED_SHORT = 0.05
GUARDRAIL_CAP = 0.25
CROWDING_HAIRCUT = 0.5


# --- reaction functions -----------------------------------------------------------


def reaction(z: pd.Series) -> pd.Series:
    """Bouchouev's reaction function, `R(z) = z * exp(0.5 * (1 - z**2))`.

    Conviction rises to a peak of exactly 1 at `z = 1`, then *falls* as the signal grows
    more extreme -- an unusually large reading is treated as a regime the model does not
    understand rather than an unusually good opportunity. Input is clipped to [-3, 3] per
    the spec, so a tail reading holds the tail value instead of decaying to nothing.
    """
    clipped = z.clip(-REACTION_CLIP, REACTION_CLIP)
    out: pd.Series = clipped * np.exp(0.5 * (1.0 - clipped**2))
    return out


def reaction_piecewise(z: pd.Series, plateau: float = 1.0, cutoff: float = 2.5) -> pd.Series:
    """Linear ramp to `plateau`, flat until `cutoff`, then flat zero beyond it.

    The blunt cousin of `reaction`: same "extreme means stand aside" intent, but the
    cut is explicit rather than smooth, which makes it easier to reason about in a
    backtest attribution.
    """
    magnitude = z.abs()
    ramp = magnitude.clip(upper=plateau) / plateau
    inside = magnitude <= cutoff
    out: pd.Series = np.sign(z) * ramp * inside
    return out


# --- carry ------------------------------------------------------------------------


def _rank(unadj: pd.DataFrame, rank: int) -> pd.Series:
    column = f"f{rank:02d}"
    if column not in unadj.columns:
        raise KeyError(
            f"rank {column!r} is not in the panel (has {list(unadj.columns)}). "
            "EIA publishes ranks 1-4 only."
        )
    return unadj[column]


def carry(unadj: pd.DataFrame, near: int = 1, far: int = 13) -> pd.Series:
    """`F_near - F_far`, positive in backwardation. Unadjusted ranks only -- a spread
    from a back-adjusted series is meaningless (the conventions' own rule)."""
    return _rank(unadj, near) - _rank(unadj, far)


def carry_pct(unadj: pd.DataFrame, near: int = 1, far: int = 13) -> pd.Series:
    """Carry as an annualised rate on the deferred leg.

    The legs are `far - near` months apart, so the raw proportional spread annualises by
    `12 / (far - near)` -- a two-month spread is scaled by 6, not by 12.
    """
    if far == near:
        raise ValueError("near and far must differ")
    deferred = _rank(unadj, far)
    raw = carry(unadj, near, far) / deferred
    return raw * (MONTHS_PER_YEAR / (far - near))


def momentum_on_carry(carry_series: pd.Series, n: int = 60) -> pd.Series:
    """Carry relative to its own trailing mean -- is the curve tightening or loosening?"""
    return carry_series - carry_series.rolling(n).mean()


# --- price signals ----------------------------------------------------------------


def log_price(prices: pd.Series) -> pd.Series:
    """`log(price)`, with non-positive prices returned as NaN instead of a warning.

    WTI genuinely settled at **-$37.63 on 2020-04-20** and the lake holds that real
    print (this project already records it in `pipelines/macro/NOTES.md`, where a naive
    "every price is positive" test failed against the same day). A log return is
    undefined there, so it is NaN by construction rather than a RuntimeWarning plus a
    silently propagated NaN. The gap is confined to the windows that actually touch the
    negative print.
    """
    return pd.Series(
        np.where(prices > 0, np.log(prices.where(prices > 0)), np.nan),
        index=prices.index,
        name=prices.name,
    )


def momentum_ma(f01_adj: pd.Series, n: int = 100) -> pd.Series:
    """Price less its own `n`-day moving average. Back-adjusted front month only: a raw
    rank series would score the roll step as momentum."""
    return f01_adj - f01_adj.rolling(n).mean()


def momentum_ret(f01_adj: pd.Series, n: int = 252) -> pd.Series:
    """Trailing `n`-day log return."""
    out: pd.Series = log_price(f01_adj).diff(n)
    return out


def value(f01_adj: pd.Series, n: int = 1260) -> pd.Series:
    """Deviation from a long-run (default five-year) mean, signed so that **cheap is
    positive**.

    Deliberately the opposite sign to `momentum_ma` on the same input: value buys what
    momentum is selling, which is why the spec uses it as an overlay rather than as a
    standalone signal.
    """
    logged = log_price(f01_adj)
    deviation = logged - logged.rolling(n).mean()
    signal: pd.Series = -deviation / logged.rolling(n).std()
    return signal


def convexity_signal(unadj: pd.DataFrame) -> pd.Series:
    """`sign(cv123)` from `core.curve.convexity` -- imported, not recomputed."""
    return pd.Series(np.sign(convexity(unadj)), index=unadj.index, name="convexity_signal")


# --- normalisation and sizing -----------------------------------------------------


def zscore(x: pd.Series, window: int = 252) -> pd.Series:
    """**Rolling** z-score over `window` observations.

    Not `core.macro.zscore`, which is deliberately a full-sample z for a different
    purpose (indexing a published macro series against its own whole history). A
    full-sample z inside a trading signal would use the future.
    """
    rolling = x.rolling(window)
    return (x - rolling.mean()) / rolling.std()


def vol_target(
    returns: pd.Series, target_ann: float = 0.10, window: int = 63
) -> pd.Series:
    """Scale factor bringing realised volatility onto `target_ann`.

    `target / realised`, so it scales *down* when the market is wilder than the target and
    *up* when it is calmer. Realised vol is a trailing `window`-day standard deviation
    annualised by sqrt(252) -- a plain estimator, and the placeholder the spec names until
    Spec 22's own realised vol exists.
    """
    realised = returns.rolling(window).std() * np.sqrt(TRADING_DAYS)
    scale: pd.Series = (target_ann / realised).replace([np.inf, -np.inf], np.nan)
    return scale


def blend(signals: dict[str, pd.Series], weights: dict[str, float]) -> pd.Series:
    """Weighted sum of already-normalised signals. A weight naming a signal that was not
    supplied is an error, not a silently dropped term."""
    missing = set(weights) - set(signals)
    if missing:
        raise KeyError(f"weights name signals that were not supplied: {sorted(missing)}")

    frame = pd.DataFrame({name: signals[name] for name in weights})
    return frame.mul(pd.Series(weights), axis=1).sum(axis=1, min_count=1)


def position(blended_z: pd.Series, sizing: str = "reaction") -> pd.Series:
    """Normalised signal -> a position in [-1, 1].

    `reaction` and `piecewise` are bounded by 1 by construction; `sign` and `linear` are
    clipped. Every rule returns the same units so strategies stay comparable.
    """
    if sizing == "reaction":
        raw = reaction(blended_z)
    elif sizing == "piecewise":
        raw = reaction_piecewise(blended_z)
    elif sizing == "sign":
        raw = pd.Series(np.sign(blended_z), index=blended_z.index)
    elif sizing == "linear":
        raw = blended_z
    else:
        raise ValueError(
            f"unknown sizing rule {sizing!r} -- expected reaction, piecewise, sign or linear"
        )
    return raw.clip(-1.0, 1.0)


# --- guardrails -------------------------------------------------------------------


def apply_guardrails(
    pos: pd.Series, util_decile: pd.Series, cot_pct: pd.Series
) -> pd.Series:
    """Cap positions that lean the same way the physical state and the crowd already do.

    - Cushing utilisation in the **top** decile already implies contango, so a short
      position (the consensus trade in that state) is capped at `GUARDRAIL_CAP`.
    - Utilisation in the **bottom** decile implies backwardation, so a long is capped.
    - Managed money above the 95th percentile long halves longs; below the 5th halves
      shorts. Directional on purpose -- a crowded long says nothing about the risk of
      being short.

    Both families compose: a position can be capped *and* halved. The spec's own wording
    for the low-utilisation case ("cap long-backwardation/short-spread") names the trade
    twice; it is read here as the symmetric counterpart of the high-utilisation rule,
    capping the position the inventory state already favours.

    A missing conditioner leaves the position untouched -- an absent decile must never
    silently flatten a real signal.
    """
    out = pos.astype(float).copy()
    util = util_decile.reindex(out.index)
    cot = cot_pct.reindex(out.index)

    full_tanks = (util >= FULL_TANKS_DECILE).fillna(False) & (out < 0)
    out = out.mask(full_tanks, out.clip(lower=-GUARDRAIL_CAP))

    empty_tanks = (util <= EMPTY_TANKS_DECILE).fillna(False) & (out > 0)
    out = out.mask(empty_tanks, out.clip(upper=GUARDRAIL_CAP))

    crowded_long = (cot > CROWDED_LONG).fillna(False) & (out > 0)
    out = out.mask(crowded_long, out * CROWDING_HAIRCUT)

    crowded_short = (cot < CROWDED_SHORT).fillna(False) & (out < 0)
    out = out.mask(crowded_short, out * CROWDING_HAIRCUT)

    return out
