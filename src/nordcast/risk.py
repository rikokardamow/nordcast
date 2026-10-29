"""L3: what the L2 strategy could have lost, and whether the risk model knew.

Value at risk on the daily net P&L (EUR) of a strategy, with backtests:

- hs_var: historical simulation over a trailing window, the control that is
  expected to fail (Lyu et al. 2024, the source spec 22 in supply-or-demand
  follows, has it failing every test).
- garch_t_var, garch_evt_var: GARCH(1,1) on the daily P&L, fitted by Gaussian
  quasi-maximum likelihood in scipy (spec 22: "scipy MLE, no R"), with the
  standardised residuals' loss tail from a Student t, or from a generalised
  Pareto fitted above the empirical 10 % threshold (peaks over threshold).
- kupiec_uc, christoffersen_cc: unconditional coverage and conditional
  coverage (independence) likelihood-ratio tests.

Not built: the MIDAS long-run component. Spec 22 drives it with a monthly macro
series over a ~2,000-day window; this strategy has about a year of daily P&L,
not enough to identify a long-run component, and the notes' stand-in (daily
wind-forecast-error variance) can wait for a longer record.

Every VaR here is a positive EUR loss for day t, built only from days before
t. A day is an exception when its P&L is below -VaR.

The risk functions are written fresh: supply-or-demand's core/risk.py, which the
layer notes name, doesn't exist at the commit the other layers were copied from.
"""

import numpy as np
import pandas as pd
from scipy import optimize, stats

EVT_TAIL = 0.10  # threshold at the empirical 10 % of the loss tail (spec 22)


def hs_var(pnl, q, window):
    """Historical simulation: minus the q-quantile of the previous `window` days."""
    return -pnl.shift(1).rolling(window).quantile(q)


def _garch_nll(params, e):
    omega, alpha, beta = params
    s2 = np.empty_like(e)
    s2[0] = e.var()
    for t in range(1, len(e)):
        s2[t] = omega + alpha * e[t - 1] ** 2 + beta * s2[t - 1]
    if (s2 <= 0).any():
        return 1e12
    return 0.5 * np.sum(np.log(s2) + e**2 / s2)


def fit_garch(r):
    """GARCH(1,1) on r by Gaussian QML. Returns mu, omega, alpha, beta, the
    conditional sd path, the standardised residuals and next day's sd."""
    r = np.asarray(r, dtype=float)
    mu = r.mean()
    e = r - mu
    var = e.var()
    res = optimize.minimize(
        _garch_nll,
        x0=[0.1 * var, 0.1, 0.8],
        args=(e,),
        bounds=[(1e-9 * var, 10 * var), (0.0, 0.999), (0.0, 0.999)],
        constraints=[{"type": "ineq", "fun": lambda p: 0.999 - p[1] - p[2]}],
        method="SLSQP",
    )
    omega, alpha, beta = res.x
    s2 = np.empty_like(e)
    s2[0] = var
    for t in range(1, len(e)):
        s2[t] = omega + alpha * e[t - 1] ** 2 + beta * s2[t - 1]
    sd = np.sqrt(s2)
    nxt = np.sqrt(omega + alpha * e[-1] ** 2 + beta * s2[-1])
    return {"mu": mu, "omega": omega, "alpha": alpha, "beta": beta,
            "sd": sd, "z": e / sd, "next_sd": nxt}  # fmt: skip


def evt_tail(z, u_q=EVT_TAIL):
    """Generalised Pareto fitted to the losses (-z) above their (1 - u_q) quantile."""
    losses = -np.asarray(z, dtype=float)
    u = np.quantile(losses, 1 - u_q)
    excess = losses[losses > u] - u
    xi, _, psi = stats.genpareto.fit(excess, floc=0)
    return {"xi": xi, "psi": psi, "u": u, "n_exceed": len(excess), "n": len(losses)}


def evt_quantile(tail, q):
    """Loss quantile of -z at tail probability q from the fitted GPD."""
    ratio = tail["n"] / tail["n_exceed"] * q
    if abs(tail["xi"]) < 1e-9:
        return tail["u"] - tail["psi"] * np.log(ratio)
    return tail["u"] + tail["psi"] / tail["xi"] * (ratio ** (-tail["xi"]) - 1)


def _rolling(pnl, q, window, refit_every, tail_quantile):
    """VaR for each day from a GARCH fitted on the `window` days before it,
    refitted every `refit_every` days and rolled forward in between."""
    r = pnl.to_numpy(dtype=float)
    out = np.full(len(r), np.nan)
    fit = None
    for t in range(window, len(r)):
        past = r[t - window : t]
        if fit is None or (t - window) % refit_every == 0:
            fit = fit_garch(past)
            zq = tail_quantile(fit["z"], q)
        else:  # roll the variance one day with yesterday's shock, same parameters
            e = r[t - 1] - fit["mu"]
            fit["next_sd"] = np.sqrt(
                fit["omega"] + fit["alpha"] * e**2 + fit["beta"] * fit["next_sd"] ** 2
            )
        out[t] = -(fit["mu"] - fit["next_sd"] * zq)
    return pd.Series(out, index=pnl.index)


def garch_t_var(pnl, q, window, refit_every=5):
    def tail(z, q):
        df, loc, scale = stats.t.fit(z)
        return -stats.t.ppf(q, df, loc, scale)

    return _rolling(pnl, q, window, refit_every, tail)


def garch_evt_var(pnl, q, window, refit_every=5):
    return _rolling(
        pnl, q, window, refit_every, lambda z, q: evt_quantile(evt_tail(z), q)
    )


def kupiec_uc(exceptions, n, q):
    """Unconditional coverage: are there as many exceptions as q says?"""
    x = int(exceptions)
    pi = x / n if n else 0.0

    def ll(p):
        return (n - x) * np.log(1 - p) + (x * np.log(p) if x else 0.0)

    lr = -2 * (ll(q) - (ll(pi) if 0 < pi < 1 else 0.0))
    return {
        "exceptions": x,
        "n": n,
        "expected": q * n,
        "lr": lr,
        "p": 1 - stats.chi2.cdf(lr, 1),
    }


def christoffersen_cc(hits, q):
    """Conditional coverage: right count *and* no clustering (Markov independence)."""
    h = np.asarray(hits, dtype=int)
    n00 = int(((h[:-1] == 0) & (h[1:] == 0)).sum())
    n01 = int(((h[:-1] == 0) & (h[1:] == 1)).sum())
    n10 = int(((h[:-1] == 1) & (h[1:] == 0)).sum())
    n11 = int(((h[:-1] == 1) & (h[1:] == 1)).sum())
    p01 = n01 / (n00 + n01) if n00 + n01 else 0.0
    p11 = n11 / (n10 + n11) if n10 + n11 else 0.0
    p = (n01 + n11) / (n00 + n01 + n10 + n11)

    def ll(prob, stay, move):
        out = 0.0
        if stay:
            out += stay * np.log(1 - prob) if prob < 1 else -np.inf
        if move:
            out += move * np.log(prob) if prob > 0 else -np.inf
        return out

    lr_ind = -2 * (ll(p, n00 + n10, n01 + n11) - ll(p01, n00, n01) - ll(p11, n10, n11))
    uc = kupiec_uc(h.sum(), len(h), q)
    lr = uc["lr"] + lr_ind
    return {"lr_ind": lr_ind, "lr": lr, "p": 1 - stats.chi2.cdf(lr, 2)}


MODELS = {
    "historical simulation": hs_var,
    "garch-t": garch_t_var,
    "garch-evt": garch_evt_var,
}


def compare_models(pnl, qs=(0.01, 0.05), window=120):
    """Exceptions and both tests per model and quantile, on the days every model
    covers. `pass` means neither test rejects at 5 %."""
    var = {(m, q): f(pnl, q, window) for m, f in MODELS.items() for q in qs}
    common = pd.concat(var.values(), axis=1).dropna().index
    rows = []
    for (m, q), v in var.items():
        hits = (pnl.loc[common] < -v.loc[common]).astype(int)
        uc, cc = kupiec_uc(hits.sum(), len(hits), q), christoffersen_cc(hits, q)
        rows.append({"model": m, "q": q, "days": len(hits), "exceptions": int(hits.sum()),
                     "expected": q * len(hits), "uc_p": uc["p"], "cc_p": cc["p"],
                     "pass": uc["p"] > 0.05 and cc["p"] > 0.05})  # fmt: skip
    return pd.DataFrame(rows), var
