"""The Spec 21 strategy registry: eight named strategies built from `core/systematic.py`.

Pure maths only. `pipelines/derived/systematic.py` reads the lake, calls `build_positions`
and writes `derived.pos.<strategy>.<root>`.

**Two entries cannot run on the lake's current futures data, and say so rather than
substituting a shorter spread.** `CARRY_1_13` needs rank 13 and `FWD_SPREAD_MR` needs
rank 7; EIA's discontinued NYMEX route publishes ranks 1-4 only. `missing_ranks` reports
what each strategy lacks and `available_strategies` filters the registry to what a given
panel can actually support, so a strategy is either run honestly or visibly skipped --
never quietly reinterpreted. Relabelling a C(1,3) result as the paper's C(1,13) anchor
would be the one genuinely misleading outcome here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from nordcast.layers.systematic import (
    apply_guardrails,
    blend,
    carry,
    carry_pct,
    convexity_signal,
    log_price,
    momentum_ma,
    momentum_on_carry,
    position,
    value,
    vol_target,
    zscore,
)

VALUE_OVERLAY_THRESHOLD = 1.5
VALUE_OVERLAY_STRENGTH = 0.5

# The book states 1993-2022 throughout: Fig. 5.1 and Fig. 5.6 are both captioned
# "(1993-2022)", and the static-spread result is "the thirty-year period starting from
# 1993" (p.112). An earlier transcription of this said 1992-2022; verified against the
# source on 2026-09-05 and corrected.
_BOUCHOUEV = "Bouchouev, Virtual Barrels, ch. 5-6 (1993-2022, unleveraged)"


@dataclass(frozen=True)
class Benchmark:
    """A published figure shown beside the repo estimate, with its source (root
    NOTES.md: "Published literature benchmarks are shown beside repo estimates with the
    deviation."). Carried on the registry entry itself, independent of whether today's
    lake can actually build that strategy -- CARRY_1_13's anchor is real literature for
    what CARRY_1_13 *is*, even while the strategy itself is gated off for lack of rank 13.
    """

    ann_return: float
    sharpe: float
    source: str


@dataclass(frozen=True)
class StrategyInputs:
    """Everything the registry can draw on, already aligned on one index."""

    unadj: pd.DataFrame
    f01_adj: pd.Series
    util_decile: pd.Series | None = None
    cot_pct: pd.Series | None = None

    def guardrail_inputs(self) -> tuple[pd.Series, pd.Series]:
        """Missing conditioners become all-NaN, which `apply_guardrails` leaves alone --
        an absent decile must never silently flatten a real position."""
        index = self.unadj.index
        util = (
            self.util_decile
            if self.util_decile is not None
            else pd.Series(np.nan, index=index)
        )
        cot = (
            self.cot_pct if self.cot_pct is not None else pd.Series(np.nan, index=index)
        )
        return util.reindex(index), cot.reindex(index)


@dataclass(frozen=True)
class Strategy:
    name: str
    required_ranks: tuple[int, ...]
    traded: str
    build: Callable[[StrategyInputs], pd.Series]
    note: str = ""
    benchmark: Benchmark | None = None


def _carry_z(data: StrategyInputs, near: int, far: int) -> pd.Series:
    return zscore(carry_pct(data.unadj, near, far), window=252)


def _carry_1_13(data: StrategyInputs) -> pd.Series:
    """Sign of C(1,13), flat sizing -- the spec's own headline strategy."""
    return position(_carry_z(data, 1, 13), sizing="sign")


def _carry_react(data: StrategyInputs) -> pd.Series:
    """Reaction of z(carry_pct) with a 10% volatility target."""
    raw = position(_carry_z(data, 1, 3), sizing="reaction")
    scale = vol_target(log_price(data.f01_adj).diff(), target_ann=0.10, window=63)
    return (raw * scale.clip(upper=1.0)).clip(-1.0, 1.0)


def _mom_100(data: StrategyInputs) -> pd.Series:
    return position(
        zscore(momentum_ma(data.f01_adj, n=100), window=252), sizing="reaction"
    )


def _dynamic_carry(data: StrategyInputs) -> pd.Series:
    """Bouchouev's carry-momentum, verbatim: `pi_CM = sign(C_t - MA_t(C_t; n))`.

    Momentum applied to *carry*, not to price -- "a measure of the current state of supply
    and demand, and the change in carry as a measure of expected changes in future supply
    and demand" (Virtual Barrels p.101). This is the strategy the published 24.7% / 0.64
    anchor actually measures.

    It uses the **annual** carry C(1,13), as the book does, so it needs rank 13 and gates
    off on a four-rank panel exactly like CARRY_1_13. That is the honest outcome: the
    anchor belongs to a strategy that cannot be run on this lake, rather than being
    attached to one that can and did not produce it.
    """
    return position(momentum_on_carry(carry(data.unadj, 1, 13), n=60), sizing="sign")


def _carry_mom(data: StrategyInputs) -> pd.Series:
    """A 50/50 blend of carry and PRICE momentum, sized through the reaction function.

    This is the spec's own construction and is **not** Bouchouev's carry-momentum, which
    applies momentum to carry itself -- see `_dynamic_carry`. It therefore carries no
    published benchmark: crediting this blend with the book's 24.7% / 0.64 would attribute
    to it a result produced by a different strategy.
    """
    blended = blend(
        {
            "carry": _carry_z(data, 1, 3),
            "momentum": zscore(momentum_ma(data.f01_adj, n=100), window=252),
        },
        {"carry": 0.5, "momentum": 0.5},
    )
    return position(blended, sizing="reaction")


def _convex_spread(data: StrategyInputs) -> pd.Series:
    """sign(cv123) traded on s12, with the physical and crowding guardrails applied."""
    raw = convexity_signal(data.unadj)
    util, cot = data.guardrail_inputs()
    return apply_guardrails(raw.clip(-1.0, 1.0), util, cot)


def _short_spread_static(data: StrategyInputs) -> pd.Series:
    """Constant -1 on s12. The spec's benchmark leg, not a signal."""
    return pd.Series(-1.0, index=data.unadj.index)


def _fwd_spread_mr(data: StrategyInputs) -> pd.Series:
    """Mean-reversion of the deferred spread S(k, k+1) against the front spread s12.

    Long the deferred spread when it sits below s12, short when above, averaged over
    k in {3, 6} -- which is why rank 7 is required.
    """
    s12 = data.unadj["f01"] - data.unadj["f02"]
    legs = [
        zscore(
            s12 - (data.unadj[f"f{k:02d}"] - data.unadj[f"f{k + 1:02d}"]), window=252
        )
        for k in (3, 6)
    ]
    averaged = pd.concat(legs, axis=1).mean(axis=1)
    return position(averaged, sizing="reaction")


def _value_overlay(data: StrategyInputs) -> pd.Series:
    """Momentum, scaled by (1 + 0.5 * sign(value)) wherever the value signal is strong.

    An overlay, not a standalone strategy: where |z(value)| <= 1.5 the base position is
    returned untouched.
    """
    base = _mom_100(data)
    value_z = zscore(value(data.f01_adj, n=1260), window=252)
    strong = value_z.abs() > VALUE_OVERLAY_THRESHOLD
    multiplier = 1.0 + VALUE_OVERLAY_STRENGTH * np.sign(value_z).where(strong, 0.0)
    out: pd.Series = (base * multiplier).clip(-1.0, 1.0)
    return out


REGISTRY: dict[str, Strategy] = {
    "CARRY_1_13": Strategy(
        "CARRY_1_13",
        (1, 13),
        "outright",
        _carry_1_13,
        "Bouchouev's headline carry. Needs rank 13; EIA publishes 1-4.",
        Benchmark(0.203, 0.53, _BOUCHOUEV),
    ),
    "CARRY_REACT": Strategy(
        "CARRY_REACT",
        (1, 3),
        "outright",
        _carry_react,
        "C(1,3), not the paper's C(1,13).",
    ),
    "MOM_100": Strategy("MOM_100", (1,), "outright", _mom_100),
    "CARRY_MOM": Strategy(
        "CARRY_MOM",
        (1, 3),
        "outright",
        _carry_mom,
        "Blend of C(1,3) carry and price momentum. NOT Bouchouev's carry-momentum, "
        "which applies momentum to carry itself -- see DYNAMIC_CARRY. No published "
        "anchor applies to this construction.",
        None,
    ),
    "DYNAMIC_CARRY": Strategy(
        "DYNAMIC_CARRY",
        (1, 13),
        "outright",
        _dynamic_carry,
        "Bouchouev's carry-momentum, sign(C - MA(C)) on the annual carry C(1,13). "
        "Needs rank 13; EIA publishes 1-4.",
        Benchmark(0.247, 0.64, _BOUCHOUEV),
    ),
    "CONVEX_SPREAD": Strategy("CONVEX_SPREAD", (1, 2, 3), "spread", _convex_spread),
    "SHORT_SPREAD_STATIC": Strategy(
        "SHORT_SPREAD_STATIC",
        (1, 2),
        "spread",
        _short_spread_static,
        "Benchmark leg.",
        Benchmark(float("nan"), 0.50, _BOUCHOUEV + " -- IR 0.50"),
    ),
    "FWD_SPREAD_MR": Strategy(
        "FWD_SPREAD_MR",
        (1, 2, 3, 4, 6, 7),
        "spread",
        _fwd_spread_mr,
        "Needs S(6,7), so rank 7; EIA publishes 1-4.",
    ),
    "VALUE_OVERLAY": Strategy("VALUE_OVERLAY", (1,), "outright", _value_overlay),
}


def missing_ranks(strategy: Strategy, unadj: pd.DataFrame) -> tuple[int, ...]:
    """Ranks the strategy needs that the panel does not carry."""
    return tuple(r for r in strategy.required_ranks if f"f{r:02d}" not in unadj.columns)


def available_strategies(unadj: pd.DataFrame) -> list[str]:
    """Registry entries this panel can actually support, in registry order."""
    return [name for name, s in REGISTRY.items() if not missing_ranks(s, unadj)]


def build_positions(name: str, data: StrategyInputs) -> pd.Series:
    """Positions for one strategy. Raises rather than returning an empty series when a
    required rank is absent -- a silent flat series would read as a real decision."""
    if name not in REGISTRY:
        raise KeyError(
            f"unknown strategy {name!r} -- expected one of {sorted(REGISTRY)}"
        )
    strategy = REGISTRY[name]
    absent = missing_ranks(strategy, data.unadj)
    if absent:
        needed = ", ".join(f"f{r:02d}" for r in absent)
        raise KeyError(
            f"{name} needs rank(s) {needed}, which the panel does not have "
            f"(has {list(data.unadj.columns)}). {strategy.note}"
        )
    return strategy.build(data).rename(name)
