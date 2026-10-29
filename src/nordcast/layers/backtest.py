"""Vectorised backtester and attribution analytics (Spec 21 Session B).

Pure maths only -- never touches DuckDB. Reused by Specs 20/24/25/26/27, so the contract
here is deliberately narrow: positions in, a P&L series and a stats dict out.

This replaces the deliberate stand-in `core.vecm.backtest_positions`, which Spec 20
Session C had to build because this module did not exist yet. Unlike that one, this
charges costs and reports the full stat set.

**Positions are lagged one day, always.** A position formed on day *t* earns day *t+1*'s
return. That single `shift(1)` is what separates a backtest from a curve fit, and
`tests/test_core_backtest.py` guards it two ways: a constant long must reproduce
buy-and-hold exactly, and shifting the return series must change the P&L.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

TRADING_DAYS = 252
ROLLING_SHARPE_WINDOW = 756
"""Three years of trading days, the spec's own rolling-Sharpe window."""

BPS = 1e-4
MIN_REGRESSION_OBS = 30


@dataclass(frozen=True)
class BacktestResult:
    """Daily net P&L plus the summary the spec's model cards display."""

    pnl: pd.Series
    equity: pd.Series
    drawdown: pd.Series
    positions: pd.Series
    stats: dict[str, float] = field(default_factory=dict)
    worst_days: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    rolling_sharpe: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))


def backtest(
    pos: pd.Series,
    f01_adj_log_returns: pd.Series,
    spread_pnl: pd.Series | None = None,
    cost_bps: float = 2.0,
) -> BacktestResult:
    """Run `pos` against a return stream and report P&L and statistics.

    `spread_pnl` replaces the price return entirely when supplied -- a calendar-spread
    strategy earns the change in the spread, not the front month's own return. It must
    already be in **return units**; use `spread_to_return` rather than dividing a dollar
    spread change by the spot price, which explodes when the price nears zero.

    Costs are charged on **position changes**, not on holdings: keeping a position costs
    nothing, trading it costs `cost_bps` of the traded notional.
    """
    earned = f01_adj_log_returns if spread_pnl is None else spread_pnl
    frame = pd.DataFrame({"pos": pos, "earned": earned}).sort_index()

    lagged = frame["pos"].shift(1)
    gross = lagged * frame["earned"]
    traded = frame["pos"].diff().abs()
    cost = traded * cost_bps * BPS
    pnl = (gross - cost).fillna(0.0)

    equity = pnl.cumsum()
    drawdown = equity - equity.cummax()

    active = pnl[lagged.fillna(0.0) != 0.0]
    ann_return = float(pnl.mean() * TRADING_DAYS)
    ann_vol = float(pnl.std() * np.sqrt(TRADING_DAYS))
    max_dd = float(drawdown.min())

    stats = {
        "ann_log_return": ann_return,
        "ann_vol": ann_vol,
        "sharpe": ann_return / ann_vol if ann_vol else float("nan"),
        "max_drawdown": max_dd,
        # Calmar is return over the *depth* of the worst drawdown, so the sign is flipped
        # to keep a profitable strategy's Calmar positive.
        "calmar": ann_return / abs(max_dd) if max_dd else float("nan"),
        "hit_rate": float((active > 0).mean()) if len(active) else float("nan"),
        "turnover": float(traded.mean() * TRADING_DAYS),
        "n_days": len(pnl),
        "total_pnl": float(pnl.sum()),
        "cost_bps": cost_bps,
    }

    rolling = pnl.rolling(ROLLING_SHARPE_WINDOW)
    rolling_sharpe = (rolling.mean() * TRADING_DAYS) / (rolling.std() * np.sqrt(TRADING_DAYS))

    return BacktestResult(
        pnl=pnl,
        equity=equity,
        drawdown=drawdown,
        positions=lagged,
        stats=stats,
        worst_days=pnl.nsmallest(5).sort_values(),
        rolling_sharpe=rolling_sharpe.replace([np.inf, -np.inf], np.nan),
    )


def spread_to_return(
    spread: pd.Series, price: pd.Series, window: int = 252
) -> pd.Series:
    """Dollar spread changes -> return-equivalent P&L, on a **stable** notional.

    `backtest`'s `spread_pnl` has to be in the same units as a log return, so a dollar
    spread change must be divided by a notional. Dividing by the *spot* price is the
    obvious choice and is wrong: it explodes whenever the price approaches zero. Measured
    on the real lake, that single flaw inflated a calendar-spread strategy's annualised
    volatility from **11.6% to 93.8%**, with three days in April 2020 doing essentially
    all of it -- WTI settled at -$37.63 on the 20th and traded near $10 on the 21st.

    The notional here is instead a trailing median price over `window`, which is backward
    looking, insensitive to a single dislocation, and never near zero for a real
    commodity.
    """
    notional = price.abs().rolling(window, min_periods=window // 2).median()
    out: pd.Series = spread.diff() / notional.replace(0.0, np.nan)
    return out.replace([np.inf, -np.inf], np.nan)


# --- attribution ------------------------------------------------------------------

_FRACTIONATION_COLUMNS = ["condition", "bin", "n", "mean", "sharpe", "share_of_total"]


def fractionate(
    daily_pnl: pd.Series,
    conditioners: dict[str, pd.Series],
    bins: int | dict[str, int] = 5,
) -> pd.DataFrame:
    """Split P&L by each conditioner and report where the money actually came from.

    `share_of_total` is each bin's signed share of the strategy's total P&L, so the
    shares within a condition sum to 1 by construction -- the spec's own acceptance test.
    A conditioner with fewer distinct values than its own bin count is grouped on its own
    values rather than forced into empty quantiles; one that is entirely missing is
    skipped. `bins` is a single count shared by every conditioner, or a `{condition: n}`
    map for conditioners that need different resolutions (a 3-state regime code beside a
    continuous utilisation series, say).
    """
    rows = []
    total = daily_pnl.sum()

    for condition, raw in conditioners.items():
        aligned = raw.reindex(daily_pnl.index)
        usable = daily_pnl[aligned.notna()]
        values = aligned.dropna()
        if usable.empty:
            continue

        n_bins = bins[condition] if isinstance(bins, dict) else bins
        # Few distinct values (a regime code, a month) group on themselves; a continuous
        # conditioner is cut into quantiles.
        grouping = (
            values
            if values.nunique() <= n_bins
            else pd.qcut(values, n_bins, duplicates="drop")
        )

        for label, group in usable.groupby(grouping, observed=True):
            std = group.std()
            rows.append(
                {
                    "condition": condition,
                    "bin": str(label),
                    "n": len(group),
                    "mean": float(group.mean()),
                    "sharpe": float(group.mean() / std * np.sqrt(TRADING_DAYS))
                    if std
                    else float("nan"),
                    "share_of_total": float(group.sum() / total) if total else float("nan"),
                }
            )

    return pd.DataFrame(rows, columns=_FRACTIONATION_COLUMNS)


def _ols(y: np.ndarray, x: np.ndarray) -> tuple[float, float]:
    """Return (r-squared, t-statistic on the slope) for a simple regression."""
    design = np.column_stack([np.ones(len(x)), x])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    resid = y - design @ beta
    dof = len(y) - design.shape[1]
    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot else float("nan")

    sigma2 = ss_res / dof if dof > 0 else float("nan")
    xtx_inv = np.linalg.pinv(design.T @ design)
    se = float(np.sqrt(sigma2 * xtx_inv[1, 1])) if dof > 0 else float("nan")
    t_stat = float(beta[1] / se) if se else float("nan")
    return r2, t_stat


def inventory_predictability_test(s12: pd.Series, inventory: pd.Series) -> dict[str, float | bool]:
    """Which leads which: calendar spreads or inventories?

    Regresses the change in inventory on the lagged change in the spread, and the change
    in the spread on the lagged change in inventory. Bouchouev's finding is that spreads
    predict inventories more than the reverse, which is why the page carries this as a
    permanent caption -- it is the standing guard against naive "inventories drive
    spreads" reasoning.

    Both sides are run on **changes**, not levels: two trending levels would produce a
    high r-squared in either direction and say nothing about lead-lag.
    """
    frame = pd.DataFrame({"s12": s12, "inventory": inventory}).dropna().sort_index()
    changes = frame.diff().dropna()
    if len(changes) < MIN_REGRESSION_OBS:
        raise ValueError(
            f"need at least {MIN_REGRESSION_OBS} overlapping observations, got {len(changes)}"
        )

    spread_to_inventory = pd.DataFrame(
        {"y": changes["inventory"], "x": changes["s12"].shift(1)}
    ).dropna()
    inventory_to_spread = pd.DataFrame(
        {"y": changes["s12"], "x": changes["inventory"].shift(1)}
    ).dropna()

    r2_si, t_si = _ols(
        spread_to_inventory["y"].to_numpy(), spread_to_inventory["x"].to_numpy()
    )
    r2_is, t_is = _ols(
        inventory_to_spread["y"].to_numpy(), inventory_to_spread["x"].to_numpy()
    )

    return {
        "r2_spread_to_inventory": r2_si,
        "t_spread_to_inventory": t_si,
        "r2_inventory_to_spread": r2_is,
        "t_inventory_to_spread": t_is,
        "n_obs": len(changes),
        "spread_leads_inventory": bool(abs(t_si) > abs(t_is)),
    }
