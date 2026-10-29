"""L3 risk. The acceptance numbers are spec 22's (supply-or-demand)."""

import numpy as np
import pandas as pd
import pytest

from nordcast import risk


def test_evt_on_t4_draws_recovers_a_heavy_tail():
    z = np.random.default_rng(22).standard_t(4, 20_000)
    tail = risk.evt_tail(z)
    assert 0.15 <= tail["xi"] <= 0.35  # t(4) has xi = 1/4


def test_kupiec_matches_spec_22():
    assert risk.kupiec_uc(10, 1000, 0.01)["p"] == pytest.approx(1.0, abs=1e-6)
    assert risk.kupiec_uc(25, 1000, 0.01)["p"] < 0.01


def test_christoffersen_tells_alternating_from_clustered():
    n, k = 1000, 50
    spread = np.zeros(n, int)
    spread[:: n // k] = 1
    clustered = np.zeros(n, int)
    clustered[400 : 400 + k] = 1
    assert risk.christoffersen_cc(spread, 0.05)["p"] > 0.05
    assert risk.christoffersen_cc(clustered, 0.05)["p"] < 0.001


@pytest.mark.parametrize("model", list(risk.MODELS))
def test_var_for_a_day_never_uses_that_day_or_later(model):
    rng = np.random.default_rng(1)
    pnl = pd.Series(rng.standard_t(5, 300) * 100)
    base = risk.MODELS[model](pnl, 0.05, 120)
    shocked = pnl.copy()
    shocked.iloc[200:] = shocked.iloc[200:] * 50 - 1e6
    after = risk.MODELS[model](shocked, 0.05, 120)
    pd.testing.assert_series_equal(base.iloc[:201], after.iloc[:201])


def test_garch_recovers_its_parameters():
    rng = np.random.default_rng(7)
    omega, alpha, beta, n = 0.05, 0.10, 0.85, 4000
    r, s2 = np.empty(n), omega / (1 - alpha - beta)
    for t in range(n):
        r[t] = np.sqrt(s2) * rng.standard_normal()
        s2 = omega + alpha * r[t] ** 2 + beta * s2
    fit = risk.fit_garch(r)
    assert fit["alpha"] == pytest.approx(alpha, abs=0.05)
    assert fit["beta"] == pytest.approx(beta, abs=0.07)


def test_a_well_specified_model_passes_on_its_own_data():
    rng = np.random.default_rng(3)
    pnl = pd.Series(rng.standard_normal(1200) * 100)
    table, _ = risk.compare_models(pnl, qs=(0.05,), window=250)
    assert table.set_index("model").loc["garch-t", "pass"]
