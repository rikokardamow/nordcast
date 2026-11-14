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

import pandas as pd

from nordcast import paper_style as ps
from nordcast import pnl, positions
from nordcast.figure_utils import ATTRIBUTION, LICENCE, label_offsets
from nordcast.layers.backtest import fractionate

D = Path("../data/layers")
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
        """NAVY, BLUE, GREY = ps.PALETTE[0], ps.PALETTE[1], ps.PALETTE[2]
CPH = "Europe/Copenhagen"
fig, axes = ps.figure(2, 1, height_ratios=[3, 2])
top, bottom = axes[0][0], axes[1][0]
cums = {}
for name, colour, ls in (("forecast", BLUE, "-"), ("persistence", GREY, "--")):
    frame, c = runs[(15, name)]
    cums[name] = frame.net.fillna(0).cumsum() / 1000
    top.plot(cums[name].index.tz_convert(CPH), cums[name], color=colour, ls=ls, lw=1.0)
top.axhline(0, color=GREY, lw=0.6)
_, c = runs[(15, "forecast")]
month = c.target.dt.tz_convert(CPH).dt.tz_localize(None).dt.to_period("M")
maes = {}
for col, colour, ls, lab in (("point", BLUE, "-", "ar(1)"), ("pers_point", GREY, "--", "persistence")):
    m = (c[col] - c.y).abs().groupby(month.to_numpy()).mean()
    maes[lab] = m
    bottom.plot(m.index.to_timestamp().tz_localize(CPH) + pd.Timedelta(days=14), m, color=colour, ls=ls, marker="o", ms=2.5)
ps.frame(
    fig,
    title=(
        f"Holding into imbalance 15 min ahead made ar(1) {cums['forecast'].iloc[-1]:+.0f} kEUR net and "
        f"persistence {cums['persistence'].iloc[-1]:+.0f} kEUR over the replay year (replay, not the record)"
    ),
    subtitle=(
        "(a) Cumulative net P&L, at most 10 MW held per quarter-hour, slippage EUR 2/MWh assumed; "
        "rule: 4 Mar 2026, when SatisfiedDemand changed from demand to activated energy. "
        "(b) Mean absolute error of the call by month. Estimated vintages."
    ),
    units=["kEUR", "MW"],
    cadence="quarter-hourly",
    source=f"{ATTRIBUTION} (calls from jobs/layer_calls.py)",
    licence=LICENCE,
    asof="2026-09-30",  # the replay window ends here
    xlabel="Date, Copenhagen time",
    ylabel=["Cumulative net P&L (kEUR)", "Mean absolute error by month (MW)"],
    margins=(0.65, 1.1, 0.2, 0.5),
)
ps.event_rule(top, pd.Timestamp("2026-03-04", tz=CPH), "4 Mar 2026")
ps.date_axis(bottom)
for ax, items in (
    (top, [(cums["forecast"], "ar(1)", BLUE), (cums["persistence"], "Persistence", GREY)]),
    (bottom, [(maes["ar(1)"], "ar(1)", BLUE), (maes["persistence"], "Persistence", GREY)]),
):
    ends = []
    for s, _, _ in items:
        s = s.dropna()
        idx = s.index.tz_convert(CPH) if ax is top else s.index.to_timestamp().tz_localize(CPH) + pd.Timedelta(days=14)
        ends.append((idx[-1], float(s.iloc[-1])))
    dys = label_offsets(ax, [y for _, y in ends], gap_pt=10)
    for (s, text, colour), (x, y), dy in zip(items, ends, dys, strict=True):
        ps.end_label(ax, x, y, text, f"{y:.0f}", color=colour, dy=dy)
ps.show(fig)
ps.save(fig, "11_pnl", formats=("pdf", "png", "tex"))"""
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
