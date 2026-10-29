"""L2: what each L1 position would have made, under notes/limits.md.

Hold-into-imbalance: a position of p MW for an ISP leaves p MW open, bought at
the day-ahead price and settled at the first-print imbalance price, so it earns
p x 0.25 h x (imbalance - day-ahead) EUR. Long earns when the system is short
(up-regulation, imbalance above day-ahead).

- Gross P&L goes through layers.backtest.backtest, unchanged: it lags positions
  one step, so each position is filed on the row before its ISP and the lag
  applies it to that ISP's own spread. Its two acceptance guards are this
  module's tests.
- Costs: every ISP is a fresh trade (day-ahead bought per ISP), so slippage is
  charged on |p| x 0.25 MWh each ISP, at a stated SLIPPAGE_EUR_MWH, not on
  position changes as backtest() does.
- The daily loss limit (EUR 5,000, notes/limits.md): once a Copenhagen day's
  net P&L reaches -5,000, the position is flat from the next ISP to the end of
  that day, and the breach is logged.
- An ISP with no first-print price earns nothing and is counted, never filled.
"""

import numpy as np
import pandas as pd

from nordcast.layers.backtest import backtest

ISP_HOURS = 0.25
SLIPPAGE_EUR_MWH = 2.0  # stated assumption: day-ahead bid/offer and imbalance fees
DAILY_LOSS_LIMIT_EUR = 5_000.0  # notes/limits.md
COPENHAGEN = "Europe/Copenhagen"


def earned_per_mw(calls):
    """EUR one MW long earns over the ISP: 0.25 x (imbalance - day-ahead). NaN when
    either price is missing."""
    return ISP_HOURS * (calls.imb_price - calls.da_price_target)


def gross(pos_mw, earned):
    """Gross EUR per ISP via backtest(): positions filed one row early so its
    one-step lag lands each on its own ISP."""
    # one row before the first ISP, so the first position has a row to be filed on
    before = pos_mw.index[0] - pd.Timedelta(minutes=15)
    index = pos_mw.index.insert(0, before)
    filed = pd.Series(np.append(pos_mw.to_numpy(), np.nan), index=index)
    earned_ext = earned.reindex(index)
    out = backtest(filed.fillna(0.0), earned_ext.fillna(0.0), cost_bps=0.0).pnl
    return out.drop(before).where(earned.notna() & pos_mw.notna())


def apply_loss_limit(pos_mw, net_pnl, limit=DAILY_LOSS_LIMIT_EUR):
    """Flat from the ISP after a Copenhagen day's net P&L reaches -limit.

    Returns (positions under the limit, breaches: {day: ISP of the breach})."""
    pos = pos_mw.copy()
    breaches = {}
    day = pos.index.tz_convert(COPENHAGEN).date
    for d, idx in pd.Series(pos.index, index=pos.index).groupby(day):
        running = 0.0
        for i, isp in enumerate(idx):
            running += 0.0 if np.isnan(net_pnl[isp]) else net_pnl[isp]
            if running <= -limit:
                breaches[d] = isp
                pos.loc[idx.iloc[i + 1 :]] = pos.loc[idx.iloc[i + 1 :]].where(
                    pos.loc[idx.iloc[i + 1 :]].isna(), 0.0
                )
                break
    return pos, breaches


def run(pos_mw, calls, slippage=SLIPPAGE_EUR_MWH, limit=DAILY_LOSS_LIMIT_EUR):
    """Net P&L per ISP under the loss limit, with its parts.

    Returns a frame indexed by ISP: pos_mw (as held, after the limit), gross,
    cost, net; and the breaches."""
    earned = earned_per_mw(calls)

    def net_of(pos):
        g = gross(pos, earned)
        c = (pos.abs() * ISP_HOURS * slippage).where(g.notna())
        return g, c, g - c

    _, _, first_pass = net_of(pos_mw)
    held, breaches = apply_loss_limit(pos_mw, first_pass, limit)
    g, c, net = net_of(held)
    frame = pd.DataFrame({"pos_mw": held, "gross": g, "cost": c, "net": net})
    return frame, breaches


def summary(frame, breaches):
    """The L2 card: totals, a daily Sharpe (power trades every day: sqrt 365),
    the worst drawdown, and what was left out."""
    net = frame.net
    day = net.index.tz_convert(COPENHAGEN).date
    daily = net.groupby(day).sum(min_count=1).dropna()
    equity = daily.cumsum()
    traded = (frame.pos_mw.abs() * ISP_HOURS)[net.notna()]
    positioned = frame.pos_mw.notna() & (frame.pos_mw != 0)
    return {
        "net_eur": float(net.sum()),
        "gross_eur": float(frame.gross.sum()),
        "cost_eur": float(frame.cost.sum()),
        "days": len(daily),
        "mean_day_eur": float(daily.mean()) if len(daily) else np.nan,
        "sharpe_daily_ann": float(daily.mean() / daily.std() * np.sqrt(365))
        if len(daily) > 1 and daily.std()
        else np.nan,
        "max_drawdown_eur": float((equity - equity.cummax()).min())
        if len(daily)
        else np.nan,
        "mwh_traded": float(traded.sum()),
        "eur_per_mwh": float(net.sum() / traded.sum()) if traded.sum() else np.nan,
        "positioned_isps": int(positioned.sum()),
        "unpriced_positioned_isps": int((positioned & net.isna()).sum()),
        "loss_limit_breaches": len(breaches),
    }
