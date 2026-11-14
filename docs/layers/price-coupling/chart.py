"""Layer #31 (DK1 part) chart: price_coupling (.pdf, .png, .tex) beside this file.

    uv run --all-groups python docs/layers/price-coupling/chart.py

Top: day-ahead prices, DK1 and its four neighbours with a price on Energi
Data Service, 20-26 Oct 2026. Bottom: per border, 1 Oct 2025 - 28 Oct 2026:
share of ISPs coupled (|spread| < EUR 0.01), share at its observed limit
(#33) when split, and how often the physical flow ran toward the dearer side
when split. Reads coupling.csv and the price cache written by backtest.py.
"""

import importlib.util
from pathlib import Path

import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from nordcast import paper_style as ps
from nordcast.figure_utils import ATTRIBUTION, LICENCE, label_offsets

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("pc_bt", HERE / "backtest.py")
bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bt)

CPH = "Europe/Copenhagen"
P = ps.PALETTE
COLORS = {"DK1": P[0], "DE": P[3], "DK2": P[2], "NO2": P[1], "SE3": P[4]}
STYLES = {"DK1": "-", "DE": "-", "DK2": "--", "NO2": "-", "SE3": ":"}

raw = pd.concat(pd.read_parquet(p) for p in sorted(bt.CACHE.glob("*.parquet")))
raw["t"] = pd.to_datetime(raw.TimeUTC).dt.tz_localize("UTC").dt.tz_convert(CPH)
p = raw.pivot_table(index="t", columns="PriceArea", values="DayAheadPriceEUR")
week = p.loc["2026-10-20":"2026-10-26"]
check = pd.read_csv(HERE / "coupling.csv")

fig, axes = ps.figure(2, 1, height_ratios=[3, 2], sharex=False)
top, bottom = axes[0][0], axes[1][0]
for area in bt.AREAS:
    top.plot(week.index, week[area], color=COLORS[area], ls=STYLES[area],
             lw=1.4 if area == "DK1" else 0.9, drawstyle="steps-post",
             zorder=3 if area == "DK1" else 2)  # fmt: skip
top.xaxis.set_major_locator(mdates.DayLocator(tz=CPH))
top.xaxis.set_major_formatter(mdates.DateFormatter("%-d %b", tz=CPH))

x = np.arange(len(check))
bars = (("coupled", "Coupled (same price)", P[1]),
        ("at_limit_when_split", "At observed limit, when split", P[2]),
        ("flow_toward_dearer_when_split", "Flow toward dearer side, when split", P[3]))  # fmt: skip
for i, (col, label, color) in enumerate(bars):
    bottom.bar(
        x + (i - 1) * 0.27, 100 * check[col], width=0.27, color=color, label=label
    )
bottom.set_xticks(x, check.border)
# One legend row above the 100 % line, clear of the tallest bars (the sans type is wider).
bottom.set_ylim(0, 112)
bottom.set_yticks(range(0, 101, 20))
bottom.legend(loc="upper left", frameon=False, fontsize=7, ncol=3, borderaxespad=0.2)

ps.frame(
    fig,
    title=(
        "DK1 shared one day-ahead price with DE in "
        f"{check.coupled[check.border == 'DK1-DE'].iloc[0]:.0%} of ISPs, "
        "and with NO2 and SE3 almost never"
    ),
    subtitle=(
        "(a) Day-ahead prices, DK1 and its four neighbours with a price on Energi Data Service, "
        "20-26 Oct 2026, Copenhagen time. (b) Per border, 1 Oct 2025 - 28 Oct 2026: share of "
        "ISPs coupled (|spread| < EUR 0.01), share at its observed limit when split, and how "
        "often the physical flow ran toward the dearer side when split. Observed limit: within "
        "2 % of the border's 28-day largest flow. No NL or GB price on Energi Data Service."
    ),
    units=["EUR/MWh", "%"],
    cadence="hourly",
    source=f"{ATTRIBUTION} (DayAheadPrices, ElectricityProdex5MinRealtime; coupling.csv)",
    licence=LICENCE,
    asof="2026-10-28",  # the end of the 1 Oct 2025 - 28 Oct 2026 window
    xlabel=["Date, Copenhagen time (October 2026)", "Border"],
    ylabel=["Day-ahead price (EUR/MWh)", "Share of ISPs (%)"],
)
ends = [(week.index[-1], float(week[a].dropna().iloc[-1])) for a in bt.AREAS]
dys = label_offsets(top, [y for _, y in ends], gap_pt=9)
for area, (xe, ye), dy in zip(bt.AREAS, ends, dys, strict=True):
    ps.end_label(top, xe, ye, area, f"{ye:.0f}", color=COLORS[area], dy=dy)
ps.save(fig, HERE / "price_coupling", formats=("pdf", "png", "tex"))
