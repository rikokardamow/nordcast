"""Builds 12_risk.ipynb: L3, what the L2 strategy could have lost.

uv run --all-groups python jobs/layer_calls.py
uv run --all-groups python notebooks/build_12_risk.py
uv run --all-groups jupyter nbconvert --execute --inplace notebooks/12_risk.ipynb
"""

from pathlib import Path

import nbformat as nbf

md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell

cells = [
    md(
        "# 12 – L3 risk\n\n"
        "Value at risk on the daily net P&L of the L2 strategy, 15 min ahead, under the adopted "
        "limits (notes/limits.md), and whether each risk model knew. Persistence is the strategy "
        "with risk worth measuring (L2: ar(1) is nearly flat); ar(1) is shown beside it. Replay "
        "on estimated vintages, not the record.\n\n"
        "| card | |\n|---|---|\n"
        "| estimation window | 120 days, rolling |\n"
        "| last refit | every 5 days, rolled forward daily in between |\n"
        "| out-of-sample | yes: each day's VaR uses only earlier days |\n"
        "| benchmark | historical simulation, expected to fail (Lyu et al. 2024) |\n"
        "| exceptions | below, against expected, per model and quantile |\n"
        "| structural break | 4 Mar 2026 (SatisfiedDemand: demand → activated) |\n\n"
        "Not built: the MIDAS long-run component (a year of daily P&L can't identify one; "
        "src/nordcast/risk.py says why)."
    ),
    code(
        """from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import yaml

from nordcast import pnl, positions, risk

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
SCEN = yaml.safe_load(Path("../notes/scenarios.yaml").read_text())
CPH = "Europe/Copenhagen"

c = pd.read_parquet(D / "calls_h15.parquet").set_index("target", drop=False)
isp, daily = {}, {}
for name in ("persistence", "forecast"):
    frame, _ = pnl.run(positions.build_positions(name, c, 15), c)
    isp[name] = frame
    d = frame.net.groupby(frame.index.tz_convert(CPH).date).sum(min_count=1)
    daily[name] = d
replay_days = pd.Index(sorted(set(c.target[c.replay_window].dt.tz_convert(CPH).dt.date)))
pnl_daily = {k: v.reindex(replay_days).fillna(0.0) for k, v in daily.items()}  # a flat day is 0 EUR
pd.DataFrame({k: v.describe() for k, v in pnl_daily.items()}).round(1)"""
    ),
    md(
        "## Pass/fail: Kupiec (count) and Christoffersen (count and clustering), 5 % significance"
    ),
    code(
        """tables, vars_ = {}, {}
for name in ("persistence", "forecast"):
    tables[name], vars_[name] = risk.compare_models(pnl_daily[name], qs=(0.01, 0.05), window=120)
matrix = tables["persistence"].assign(strategy="persistence")
pd.concat([matrix, tables["forecast"].assign(strategy="ar(1)")]).set_index(
    ["strategy", "model", "q"]
)[["days", "exceptions", "expected", "uc_p", "cc_p", "pass"]].round(3)"""
    ),
    md(
        "**The number:** exceptions against expected at 1 %, persistence. With ~245 backtest days a "
        "1 % VaR expects about 2.5 exceptions, so the 1 % tests have little power; the 5 % row is "
        "the one with teeth."
    ),
    code(
        """t = tables["persistence"]
t[t.q == 0.01].set_index("model")[["exceptions", "expected"]]"""
    ),
    md(
        "## Daily P&L against its 1 % and 5 % VaR (garch-evt), with historical simulation"
    ),
    code(
        """p = pnl_daily["persistence"]
v1, v5, hs = (vars_["persistence"][k] for k in (("garch-evt", 0.01), ("garch-evt", 0.05), ("historical simulation", 0.01)))
x = pd.to_datetime(p.index)
fig, ax = plt.subplots(figsize=(11, 4.8))
ax.bar(x, p / 1000, color=[BLUE if v >= 0 else NAVY for v in p], width=1.0, alpha=0.6, label="daily net P&L")
ax.plot(x, -v5 / 1000, color=GREY, lw=1.0, label="5 % VaR, garch-evt")
ax.plot(x, -v1 / 1000, color=NAVY, lw=1.2, label="1 % VaR, garch-evt")
ax.plot(x, -hs / 1000, color=GREY, lw=1.0, ls="--", label="1 % VaR, historical simulation")
hit = p < -v1
ax.scatter(x[hit.to_numpy()], p[hit] / 1000, marker="v", color="#c0392b", zorder=3, label="1 % exception")
ax.axhline(-5, color="#c0392b", lw=0.8, ls=":")
ax.text(x[5], -5.25, "daily loss limit, EUR 5,000", fontsize=8, color="#c0392b", va="top")
ax.axvline(pd.Timestamp("2026-03-04"), color=NAVY, lw=0.8, ls=":")
ax.set_ylabel("kEUR per Copenhagen day")
ax.set_title("DK1 hold-into-imbalance (persistence, 15 min, ≤ 10 MW): VaR backtest (replay, not the record)", loc="left")
ax.legend(loc="lower left", frameon=False, ncol=3, fontsize=8)
fig.text(0.01, 0.005, "Estimated vintages; first 120 days are the estimation window. Data: Energinet, Energi Data Service.", fontsize=8, color=GREY)
fig.tight_layout()
fig.savefig("12_risk.png", dpi=150, bbox_inches="tight")"""
    ),
    md("## Stress (notes/scenarios.yaml), under the EUR 5,000 daily limit"),
    code(
        """rows = []
for name, label in (("persistence", "persistence"), ("forecast", "ar(1)")):
    frame, d = isp[name], daily[name]
    w = SCEN["storm_week"]
    days = [day for day in d.index if w["from"] <= str(day) <= w["to"]]
    storm = d.reindex(days)
    rows.append({"strategy": label, "scenario": "storm week 20-26 Oct 2026",
                 "net_eur": storm.sum(), "worst_day_eur": storm.min(), "days_covered": storm.notna().sum()})
    # feed outage: hold the position at the last call for hold_hours, no new information
    k = int(SCEN["feed_outage"]["hold_hours"] * 4)
    held = frame.pos_mw.fillna(0).copy()
    earned = pnl.earned_per_mw(c).reindex(held.index)
    worst = None
    for start in range(0, len(held) - k, k):
        block = slice(start, start + k)
        frozen = held.iloc[start] * earned.iloc[block] - abs(held.iloc[start]) * pnl.ISP_HOURS * pnl.SLIPPAGE_EUR_MWH
        loss = frozen.sum(min_count=1)
        if worst is None or (pd.notna(loss) and loss < worst[0]):
            worst = (loss, held.index[start])
    rows.append({"strategy": label, "scenario": f"feed outage, {SCEN['feed_outage']['hold_hours']} h held",
                 "net_eur": worst[0], "worst_day_eur": None, "days_covered": None,
                 "when": worst[1].tz_convert(CPH).strftime("%d %b %Y %H:%M")})
    rows.append({"strategy": label, "scenario": "worst day", "net_eur": d.min(),
                 "when": str(d.idxmin())})
pd.DataFrame(rows).set_index(["strategy", "scenario"]).round(0)"""
    ),
    md(
        "## What the stress says\n\n"
        "A feed outage is the scenario the limits don't cover. With no prints arriving, the daily "
        "loss limit can't see the loss build up, and the stale-feed guardrail only caps the "
        "position at 2.5 MW instead of flattening it; so a position held through hours of outage "
        "can lose more than the EUR 5,000 the limit is meant to stop at (the outage row above). The "
        "fix belongs to the owner of notes/limits.md: flatten, not cap, once the feed has been "
        "stale for a set time. Historical simulation, expected to fail, passes here: with ~245 "
        "backtest days the tests have little power, so that is no verdict either way."
    ),
    md(
        "## Where the sources disagree\n\n"
        "The layer notes name supply-or-demand's core/risk.py; it isn't in that repo at the commit "
        "the other layers were copied from, so src/nordcast/risk.py is written fresh to spec 22's "
        "model and tests (its acceptance numbers are the tests). The notes ask for VaR on the 15-min "
        "P&L; most ISPs hold no position, so the 15-min series is mostly zeros, and the VaR is on "
        "daily P&L instead, the horizon the loss limit is set on."
    ),
]

nb = nbf.v4.new_notebook(cells=cells)
nb.metadata["kernelspec"] = {
    "name": "python3",
    "display_name": "Python 3",
    "language": "python",
}
Path(__file__).with_name("12_risk.ipynb").write_text(nbf.writes(nb))
