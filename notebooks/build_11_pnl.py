"""Builds 11_pnl.ipynb: L2, what each L1 position would have made.

uv run --all-groups python jobs/layer_calls.py
uv run --all-groups python notebooks/build_11_pnl.py
uv run --all-groups jupyter nbconvert --execute --inplace notebooks/11_pnl.ipynb
"""

from pathlib import Path

import nbformat as nbf

md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell

cells = [
    md(
        "# 11 – L2 P&L\n\n"
        "What the L1 positions would have made, holding into imbalance: p MW left open for the "
        "ISP, bought at day-ahead and settled at the first-print imbalance price, so p × 0.25 h × "
        "(imbalance − day-ahead) EUR. Slippage EUR 2/MWh on every held MWh (stated assumption); "
        "the adopted limits (notes/limits.md): 10 MW, EUR 5,000 daily loss limit, flat for the "
        "rest of the Copenhagen day after a breach. **ar(1)**, the replay's winner, against "
        "**persistence**, 1 Oct 2025 – 30 Sep 2026, walk-forward on estimated vintages: the replay, "
        "not the record.\n\n"
        "| card | |\n|---|---|\n"
        "| estimation window | ar(1): φ and μ refit on the 7 days before each freeze; positions: the "
        "rolling week of past calls |\n"
        "| last refit | every freeze (continuous) |\n"
        "| out-of-sample | yes: walk-forward, nothing fitted on the window scored |\n"
        "| benchmark | persistence, the same construction |\n"
        "| exceptions | loss-limit breaches, counted below |\n"
        "| structural break | 4 Mar 2026 (SatisfiedDemand: demand → activated); the fractionation "
        "splits on it |"
    ),
    code(
        """from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from nordcast import pnl, positions
from nordcast.layers.backtest import fractionate

D = Path("../data/layers")
NAVY, BLUE, GREY, BAND = "#0F2A4A", "#1F5FBF", "#7D8996", "#DCE3EC"
plt.rcParams.update(
    {
        "figure.figsize": (10, 4),
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": BAND,
    }
)
LABEL = {"forecast": "ar(1)", "persistence": "persistence (control)"}

runs, rows = {}, []
for h in (15, 30, 60):
    c = pd.read_parquet(D / f"calls_h{h}.parquet").set_index("target", drop=False)
    c = c[c.replay_window]  # 1 Oct 2025 - 30 Sep 2026
    for name in ("forecast", "persistence"):
        frame, breaches = pnl.run(positions.build_positions(name, c, h), c)
        runs[(h, name)] = (frame, c)
        mae = (c.point - c.y).abs().mean() if name == "forecast" else (c.pers_point - c.y).abs().mean()
        rows.append({"h": h, "strategy": LABEL[name], "mae_mw": mae, **pnl.summary(frame, breaches)})
card = pd.DataFrame(rows).set_index(["h", "strategy"])
card[["net_eur", "gross_eur", "cost_eur", "mean_day_eur", "sharpe_daily_ann", "max_drawdown_eur",
      "mwh_traded", "eur_per_mwh", "positioned_isps", "unpriced_positioned_isps",
      "loss_limit_breaches", "mae_mw"]].round(2)"""
    ),
    md(
        "**The number:** P&L per MW of MAE improvement, (net ar(1) − net persistence) / "
        "(MAE persistence − MAE ar(1)), EUR per MW. Positive means the forecast's skill turned "
        "into money; negative means it didn't, whatever its MAE."
    ),
    code(
        """number = {}
for h in (15, 30, 60):
    f, p = card.loc[(h, "ar(1)")], card.loc[(h, "persistence (control)")]
    number[h] = (f.net_eur - p.net_eur) / (p.mae_mw - f.mae_mw)
pd.Series(number, name="EUR per MW of MAE improvement").round(1)"""
    ),
    md(
        "## Attribution: direction against slippage (no carry or vol leg in this trade)"
    ),
    code(
        """card[["gross_eur", "cost_eur", "net_eur"]].assign(
    cost_share=lambda x: x.cost_eur / x.gross_eur.abs()
).round(3)"""
    ),
    md("## Where the money came from, 15 min (fractionation of net P&L per ISP)"),
    code(
        """frac = {}
for name in ("forecast", "persistence"):
    frame, c = runs[(15, name)]
    net = frame.net.dropna()
    net = net[frame.pos_mw.loc[net.index] != 0]
    frac[LABEL[name]] = fractionate(
        net,
        {"hour": c.hour, "onshore wind error at freeze (MW)": c.wind_onshore_err_da_last,
         "after 4 Mar 2026": c.regime_activated},
        bins={"hour": 24, "onshore wind error at freeze (MW)": 5, "after 4 Mar 2026": 2},
    )[["condition", "bin", "n", "mean", "share_of_total"]]
frac["persistence (control)"].round(3)"""
    ),
    code("""frac["ar(1)"].round(3)"""),
    md(
        "## Cumulative P&L, 15 min, and the error behind it\n\n"
        "MAE sits in its own panel, not on a second axis: the energy-analyst skill (a local Claude "
        "Code reference, kept out of git) treats a dual-axis overlay as a checklist, not evidence."
    ),
    code(
        """fig, (top, bottom) = plt.subplots(2, 1, figsize=(11, 6), sharex=True, gridspec_kw={"height_ratios": [3, 2]})
for name, colour, ls in (("forecast", BLUE, "-"), ("persistence", GREY, "--")):
    frame, c = runs[(15, name)]
    cum = frame.net.fillna(0).cumsum()
    top.plot(cum.index.tz_convert("Europe/Copenhagen"), cum / 1000, color=colour, ls=ls, lw=1.2, label=LABEL[name])
top.axhline(0, color=GREY, lw=0.6)
top.axvline(pd.Timestamp("2026-03-04", tz="Europe/Copenhagen"), color=NAVY, lw=0.8, ls=":")
top.text(pd.Timestamp("2026-03-06", tz="Europe/Copenhagen"), top.get_ylim()[1] * 0.92, "4 Mar 2026: activated, not demand", fontsize=8, color=NAVY)
top.set_ylabel("cumulative net P&L, kEUR")
top.set_title("DK1 hold-into-imbalance, 15 min ahead, ≤ 10 MW (replay, not the record)", loc="left")
top.legend(loc="upper left", frameon=False)
_, c = runs[(15, "forecast")]
month = c.target.dt.tz_convert("Europe/Copenhagen").dt.tz_localize(None).dt.to_period("M")
for col, colour, ls, lab in (("point", BLUE, "-", "ar(1)"), ("pers_point", GREY, "--", "persistence")):
    m = (c[col] - c.y).abs().groupby(month.to_numpy()).mean()
    bottom.plot(m.index.to_timestamp().tz_localize("Europe/Copenhagen") + pd.Timedelta(days=14), m, color=colour, ls=ls, marker="o", ms=3, label=lab)
bottom.set_ylabel("MAE by month, MW")
bottom.legend(loc="upper right", frameon=False, ncol=2)
fig.text(0.01, 0.005, "Estimated vintages; slippage EUR 2/MWh assumed. Data: Energinet, Energi Data Service.", fontsize=8, color=GREY)
fig.tight_layout()
fig.savefig("11_pnl.png", dpi=150, bbox_inches="tight")"""
    ),
    md(
        "## What this P&L is and isn't\n\n"
        "A daily Sharpe of 8 for persistence at 15 min is not a strategy anyone could book. The "
        "calls only use what was published before each freeze, so it isn't leakage, but: the "
        "inputs are estimated vintages; EUR 2/MWh slippage is an assumption with no price impact; "
        "and a balance-responsible party is expected to aim for balance, so leaving a position "
        "open into imbalance on purpose runs against how the Danish balancing market is meant to "
        "be used (check Energinet's market regulations before treating it as a trade; not legal "
        "advice). Read the P&L as a measure of how well a call reads the system's direction, which "
        "is what the layer notes use it for, not as money on the table."
    ),
    md(
        "## Where the sources disagree\n\n"
        'The layer notes ask for slippage "at the imbalance price" without a number; EUR 2/MWh '
        "is this layer's assumption, stated, and the cost share above shows how much it matters. "
        "The copied backtester charges costs on position changes; this trade is a fresh "
        "day-ahead purchase every ISP, so costs here are on every held MWh."
    ),
]

nb = nbf.v4.new_notebook(cells=cells)
nb.metadata["kernelspec"] = {
    "name": "python3",
    "display_name": "Python 3",
    "language": "python",
}
Path(__file__).with_name("11_pnl.ipynb").write_text(nbf.writes(nb))
