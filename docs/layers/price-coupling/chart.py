"""Layer #31 (DK1 part) chart: price_coupling.png beside this file.

    uv run --all-groups python docs/layers/price-coupling/chart.py

Top: day-ahead prices, DK1 and its four neighbours with a price on Energi
Data Service, 20-26 Oct 2026. Bottom: per border, 1 Oct 2025 - 28 Oct 2026:
share of ISPs coupled (|spread| < EUR 0.01), share at its observed limit
(#33) when split, and how often the physical flow ran toward the dearer side
when split. Reads coupling.csv and the price cache written by backtest.py.
"""

import importlib.util
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("pc_bt", HERE / "backtest.py")
bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bt)

NAVY, BLUE, GREY, BAND = "#0F2A4A", "#1F5FBF", "#7D8996", "#DCE3EC"
COLORS = {"DK1": "black", "DE": NAVY, "DK2": GREY, "NO2": BLUE, "SE3": "#2A9D8F"}
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": BAND})  # fmt: skip

raw = pd.concat(pd.read_parquet(p) for p in sorted(bt.CACHE.glob("*.parquet")))
raw["t"] = (
    pd.to_datetime(raw.TimeUTC).dt.tz_localize("UTC").dt.tz_convert("Europe/Copenhagen")
)
p = raw.pivot_table(index="t", columns="PriceArea", values="DayAheadPriceEUR")
week = p.loc["2026-10-20":"2026-10-26"]
check = pd.read_csv(HERE / "coupling.csv")

fig, (top, bottom) = plt.subplots(
    2, 1, figsize=(11, 7), gridspec_kw={"height_ratios": [3, 2]}
)
for area in bt.AREAS:
    top.plot(week.index, week[area], color=COLORS[area], lw=1.6 if area == "DK1" else 0.9,
             label=area, drawstyle="steps-post", zorder=3 if area == "DK1" else 2)  # fmt: skip
top.set_ylabel("EUR/MWh")
top.set_title("Day-ahead prices, DK1 and neighbours, 20–26 Oct 2026", loc="left")
top.legend(loc="upper left", ncol=5, frameon=False, fontsize=8)

x = np.arange(len(check))
bars = (("coupled", "coupled (same price)", BLUE),
        ("at_limit_when_split", "at observed limit, when split", GREY),
        ("flow_toward_dearer_when_split", "flow toward dearer side, when split", NAVY))  # fmt: skip
for i, (col, label, color) in enumerate(bars):
    bottom.bar(
        x + (i - 1) * 0.27, 100 * check[col], width=0.27, color=color, label=label
    )
bottom.set_xticks(x, check.border)
bottom.set_ylabel("% of ISPs")
bottom.set_ylim(0, 100)
bottom.set_title("1 Oct 2025 – 28 Oct 2026", loc="left", fontsize=10)
bottom.legend(loc="upper left", frameon=False, fontsize=8, ncol=3)
fig.text(0.01, -0.02, "Source: Energinet (CC BY 4.0), DayAheadPrices and ElectricityProdex5MinRealtime. "
         "No NL or GB price on Energi Data Service. Observed limit: within 2 % of the border's 28-day largest flow.",
         fontsize=8, color=GREY)  # fmt: skip
fig.tight_layout()
fig.savefig(HERE / "price_coupling.png", dpi=150, bbox_inches="tight")
