from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from nordcast.layers.strategies import (
    REGISTRY,
    StrategyInputs,
    available_strategies,
    build_positions,
    missing_ranks,
)


def _inputs(n: int = 800, ranks: tuple[int, ...] = (1, 2, 3, 4)) -> StrategyInputs:
    """A four-rank panel, which is exactly what EIA publishes."""
    idx = pd.bdate_range("2015-01-01", periods=n)
    rng = np.random.default_rng(0)
    base = pd.Series(70 + np.cumsum(rng.normal(0, 0.5, n)), index=idx)
    unadj = pd.DataFrame({f"f{r:02d}": base - 0.4 * (r - 1) for r in ranks}, index=idx)
    return StrategyInputs(
        unadj=unadj,
        f01_adj=base,
        util_decile=pd.Series(rng.integers(0, 10, n).astype(float), index=idx),
        cot_pct=pd.Series(rng.uniform(0, 1, n), index=idx),
    )


# --- registry shape ---------------------------------------------------------------


def test_registry_holds_every_strategy_the_spec_names() -> None:
    """The spec's own eight, plus DYNAMIC_CARRY -- added after checking the book, because
    the spec's CARRY_MOM (a 0.5/0.5 carry+price-momentum blend) is not the strategy
    Bouchouev's 24.7%/0.64 figure measures. See _dynamic_carry."""
    assert set(REGISTRY) == {
        "CARRY_1_13",
        "CARRY_REACT",
        "MOM_100",
        "CARRY_MOM",
        "DYNAMIC_CARRY",
        "CONVEX_SPREAD",
        "SHORT_SPREAD_STATIC",
        "FWD_SPREAD_MR",
        "VALUE_OVERLAY",
    }


def test_every_entry_declares_what_it_trades() -> None:
    for name, strategy in REGISTRY.items():
        assert strategy.traded in {"outright", "spread"}, name


def test_carry_1_13_carries_its_published_anchor() -> None:
    """The literature anchor travels with the registry entry itself, independent of
    whether today's four-rank panel can actually build the strategy -- CARRY_1_13 is
    gated off (see test_carry_1_13_is_unavailable_on_a_four_rank_panel below), but its
    benchmark is still real literature for what CARRY_1_13 *is*."""
    bench = REGISTRY["CARRY_1_13"].benchmark
    assert bench is not None
    assert bench.ann_return == pytest.approx(0.203)
    assert bench.sharpe == pytest.approx(0.53)


def test_a_strategy_without_a_published_anchor_has_none() -> None:
    assert REGISTRY["MOM_100"].benchmark is None


# --- data availability, honestly reported -----------------------------------------


def test_carry_1_13_is_unavailable_on_a_four_rank_panel() -> None:
    """EIA publishes ranks 1-4. The spec's headline strategy needs rank 13, so it must
    report itself unavailable rather than quietly running on a shorter spread."""
    assert missing_ranks(REGISTRY["CARRY_1_13"], _inputs().unadj) == (13,)


def test_forward_spread_mean_reversion_is_unavailable_on_a_four_rank_panel() -> None:
    """FWD_SPREAD_MR needs S(6,7), so rank 7."""
    assert 7 in missing_ranks(REGISTRY["FWD_SPREAD_MR"], _inputs().unadj)


def test_available_strategies_excludes_the_two_that_need_deferred_ranks() -> None:
    names = set(available_strategies(_inputs().unadj))
    assert "CARRY_1_13" not in names
    assert "FWD_SPREAD_MR" not in names
    assert {"MOM_100", "CONVEX_SPREAD", "SHORT_SPREAD_STATIC", "VALUE_OVERLAY"} <= names


def test_everything_becomes_available_on_a_full_curve() -> None:
    full = _inputs(ranks=tuple(range(1, 14)))
    assert set(available_strategies(full.unadj)) == set(REGISTRY)


def test_building_an_unavailable_strategy_fails_loudly() -> None:
    """Silence here would be the worst outcome: a strategy that quietly returns nothing
    reads as 'flat', which is a real position, not an absence of data."""
    with pytest.raises(KeyError, match="f13"):
        build_positions("CARRY_1_13", _inputs())


def test_an_unknown_strategy_name_is_rejected() -> None:
    with pytest.raises(KeyError, match="unknown strategy"):
        build_positions("NOT_A_STRATEGY", _inputs())


# --- positions --------------------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["CARRY_REACT", "MOM_100", "CARRY_MOM", "CONVEX_SPREAD", "VALUE_OVERLAY"]
)
def test_available_strategies_produce_bounded_positions(name: str) -> None:
    pos = build_positions(name, _inputs())
    assert pos.dropna().between(-1.0, 1.0).all(), name
    assert pos.index.equals(_inputs().unadj.index)


def test_short_spread_static_is_a_constant_short() -> None:
    """The spec's own benchmark leg: -1 on s12, always."""
    pos = build_positions("SHORT_SPREAD_STATIC", _inputs())
    assert (pos == -1.0).all()


def test_convex_spread_respects_the_guardrails() -> None:
    """With utilisation pinned in the top decile, no short may exceed the 25% cap."""
    data = _inputs()
    pinned = StrategyInputs(
        unadj=data.unadj,
        f01_adj=data.f01_adj,
        util_decile=pd.Series(9.0, index=data.unadj.index),
        cot_pct=pd.Series(0.5, index=data.unadj.index),
    )
    pos = build_positions("CONVEX_SPREAD", pinned).dropna()
    assert pos[pos < 0].ge(-0.25).all()


def test_value_overlay_only_scales_on_a_strong_signal() -> None:
    """The overlay multiplies by (1 + 0.5*sign(value)) only where |z| > 1.5; elsewhere it
    must leave the base position exactly alone.

    Needs a long fixture: value() looks back 1260 days and its z-score another 252, so
    the overlay cannot fire at all before roughly six years of history.
    """
    data = _inputs(1800)
    pos = build_positions("VALUE_OVERLAY", data)
    base = build_positions("MOM_100", data)
    overlaid = (pos - base).abs() > 1e-12
    assert overlaid.any()  # it does something
    assert not overlaid.all()  # but not everywhere


def test_positions_never_use_a_future_observation() -> None:
    """Truncating the inputs must not change any position before the cut."""
    full = _inputs(800)
    cut = 600
    short = StrategyInputs(
        unadj=full.unadj.iloc[:cut],
        f01_adj=full.f01_adj.iloc[:cut],
        util_decile=full.util_decile.iloc[:cut],
        cot_pct=full.cot_pct.iloc[:cut],
    )
    for name in available_strategies(full.unadj):
        a = build_positions(name, full).iloc[:cut].to_numpy(dtype=float)
        b = build_positions(name, short).to_numpy(dtype=float)
        np.testing.assert_allclose(a, b, equal_nan=True, rtol=1e-9, err_msg=name)


def test_value_overlay_is_inert_before_it_has_enough_history() -> None:
    """With under six years of data the value leg is all-NaN, and the overlay must return
    the base position untouched rather than multiplying by NaN and flattening it."""
    data = _inputs(800)
    pd.testing.assert_series_equal(
        build_positions("VALUE_OVERLAY", data),
        build_positions("MOM_100", data),
        check_names=False,
    )


# --- DYNAMIC_CARRY: the book's actual carry-momentum ------------------------------


def test_dynamic_carry_is_registered_and_needs_the_annual_carry() -> None:
    """Bouchouev defines carry-momentum as sign(C_t - MA(C_t)) on the ANNUAL carry
    C(1,13) (Virtual Barrels p.101). That needs rank 13, so on this lake it gates off
    exactly like CARRY_1_13 -- which is the honest outcome: the 24.7%/0.64 anchor belongs
    to a strategy that cannot be run here, not to one that can.
    """
    assert "DYNAMIC_CARRY" in REGISTRY
    assert REGISTRY["DYNAMIC_CARRY"].required_ranks == (1, 13)
    assert missing_ranks(REGISTRY["DYNAMIC_CARRY"], _inputs().unadj) == (13,)


def test_the_published_carry_momentum_anchor_moved_off_carry_mom() -> None:
    """CARRY_MOM is the spec's 0.5/0.5 blend of carry and PRICE momentum -- a different
    strategy from the book's momentum-on-carry. Leaving the book's figure attached to it
    would credit our blend with a result it never produced."""
    assert REGISTRY["CARRY_MOM"].benchmark is None
    assert REGISTRY["DYNAMIC_CARRY"].benchmark is not None
    assert REGISTRY["DYNAMIC_CARRY"].benchmark.sharpe == 0.64
    assert REGISTRY["DYNAMIC_CARRY"].benchmark.ann_return == 0.247


def test_dynamic_carry_signals_on_the_change_in_carry_not_its_level() -> None:
    """sign(C - MA(C)): a steadily rising carry is a buy even while carry is negative,
    which is precisely what distinguishes it from the plain carry strategy."""
    full = _inputs(ranks=tuple(range(1, 14)))
    pos = build_positions("DYNAMIC_CARRY", full).dropna()
    assert set(np.unique(pos)).issubset({-1.0, 0.0, 1.0})


def test_every_benchmark_cites_the_period_the_book_actually_states() -> None:
    """The book says 1993-2022 throughout (Figs 5.1 and 5.6, and 'thirty-year period
    starting from 1993'). An earlier transcription said 1992-2022."""
    for name, strategy in REGISTRY.items():
        if strategy.benchmark is not None:
            assert "1993" in strategy.benchmark.source, name
            assert "1992" not in strategy.benchmark.source, name
