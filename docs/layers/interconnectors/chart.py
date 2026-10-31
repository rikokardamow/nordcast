"""Layer #33's chart: interconnectors.png beside this file.

    uv run --all-groups python docs/layers/interconnectors/chart.py

Top: DK1 physical flow by border, 20-26 Oct 2026 (the 01 notebook's week),
+ = import. Bottom: share of ISPs each border sat at its observed limit,
1 Oct 2025 - 28 Oct 2026 (within 2 % of its 28-day largest flow in that
direction; an observed limit, not a rated capacity).
"""

import importlib.util
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import psycopg

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("ic_bt", HERE / "backtest.py")
bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bt)

NAVY, BLUE, GREY, BAND = "#0F2A4A", "#1F5FBF", "#7D8996", "#DCE3EC"
COLORS = {
    "de": NAVY,
    "nl": "#E07B39",
    "gb": "#8E44AD",
    "no": BLUE,
    "se": "#2A9D8F",
    "dk2": GREY,
}
NAMES = {"de": "Germany", "nl": "Netherlands", "gb": "Great Britain", "no": "Norway",
         "se": "Sweden", "dk2": "Eastern Denmark"}  # fmt: skip
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": BAND, "axes.axisbelow": True})  # fmt: skip

with psycopg.connect(bt.DB_URL) as conn:
    frame = bt.isp_frame(conn)
frame.index = frame.index.tz_convert("Europe/Copenhagen")
week = frame.loc["2026-10-20":"2026-10-26"]
year = frame.loc["2025-10-01":"2026-10-28"]

fig, (top, bottom) = plt.subplots(
    2, 1, figsize=(11, 7), gridspec_kw={"height_ratios": [3, 2]}
)
pos = np.zeros(len(week))
neg = np.zeros(len(week))
for b in bt.BORDERS:
    v = week[b].fillna(0).to_numpy()
    up, down = np.clip(v, 0, None), np.clip(v, None, 0)
    top.fill_between(week.index, pos, pos + up, color=COLORS[b], lw=0, alpha=0.85,
                     label=NAMES[b], step="post")  # fmt: skip
    top.fill_between(week.index, neg, neg + down, color=COLORS[b], lw=0, alpha=0.85,
                     step="post")  # fmt: skip
    pos, neg = pos + up, neg + down
top.plot(
    week.index,
    week.net,
    color="black",
    lw=1.0,
    label="net import",
    drawstyle="steps-post",
)
top.axhline(0, color=GREY, lw=0.8)
top.set_ylabel("MW, 15-minute mean (+ = import)")
top.set_title("Western Denmark: power flow across each border, 20–26 Oct 2026", loc="left")
top.xaxis.set_major_formatter(mdates.DateFormatter("%-d %b", tz="Europe/Copenhagen"))
low, high = top.get_ylim()
top.set_ylim(low, high * 1.3)  # room for the legend
top.legend(loc="upper left", ncol=4, frameon=False, fontsize=8)

shares = []
for b in bt.BORDERS:
    hi = year[b].clip(lower=0).rolling("28D").max()
    lo = year[b].clip(upper=0).rolling("28D").min()
    shares.append((((year[b] > 0) & (year[b] >= bt.LIMIT * hi)).mean(),
                   ((year[b] < 0) & (year[b] <= bt.LIMIT * lo)).mean()))  # fmt: skip
x = np.arange(len(bt.BORDERS))
bottom.bar(
    x - 0.2,
    [100 * s[0] for s in shares],
    width=0.4,
    color=BLUE,
    label="at import limit",
)
bottom.bar(
    x + 0.2,
    [100 * s[1] for s in shares],
    width=0.4,
    color=NAVY,
    label="at export limit",
)
bottom.set_xticks(x, [NAMES[b] for b in bt.BORDERS])
bottom.set_ylabel("% of quarter-hours")
bottom.set_title(
    "Share of time each border ran at its recent maximum, 1 Oct 2025 – 28 Oct 2026", loc="left", fontsize=10
)
bottom.legend(loc="upper right", frameon=False, fontsize=8)
fig.text(0.01, -0.02, "Source: Energinet (CC BY 4.0), ElectricityProdex5MinRealtime, first prints. "
         "Observed limit: within 2 % of the border's largest flow in that direction over the past 28 days; "
         "not a rated capacity.", fontsize=8, color=GREY)  # fmt: skip
fig.tight_layout()
fig.savefig(HERE / "interconnectors.png", dpi=150, bbox_inches="tight")
any_limit = ((year.n_limit_import + year.n_limit_export) > 0).mean()
print(f"ISPs with any border at its limit: {any_limit:.1%}")
