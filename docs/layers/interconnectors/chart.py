"""Layer #33's chart: interconnectors (.pdf, .png, .tex) beside this file.

    uv run --all-groups python docs/layers/interconnectors/chart.py

Top: DK1 physical flow by border, 20-26 Oct 2026 (the 01 notebook's week),
+ = import. Bottom: share of ISPs each border sat at its observed limit,
1 Oct 2025 - 28 Oct 2026 (within 2 % of its 28-day largest flow in that
direction; an observed limit, not a rated capacity).
"""

import importlib.util
from pathlib import Path

import matplotlib.dates as mdates
import numpy as np
import psycopg

from nordcast import paper_style as ps
from nordcast.figure_utils import ATTRIBUTION, LICENCE, label_offsets, name_label

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("ic_bt", HERE / "backtest.py")
bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bt)

CPH = "Europe/Copenhagen"
P = ps.PALETTE
COLORS = {"de": P[0], "nl": P[3], "gb": P[5], "no": P[1], "se": P[4], "dk2": P[2]}
NAMES = {"de": "Germany", "nl": "Netherlands", "gb": "Great Britain", "no": "Norway",
         "se": "Sweden", "dk2": "DK2 (Great Belt)"}  # fmt: skip

with psycopg.connect(bt.DB_URL) as conn:
    frame = bt.isp_frame(conn)
frame.index = frame.index.tz_convert(CPH)
week = frame.loc["2026-10-20":"2026-10-26"]
year = frame.loc["2025-10-01":"2026-10-28"]

fig, axes = ps.figure(2, 1, height_ratios=[3, 2], sharex=False)
top, bottom = axes[0][0], axes[1][0]
pos = np.zeros(len(week))
neg = np.zeros(len(week))
mids = []  # where each border's band sits at the last ISP, for its direct label
for b in bt.BORDERS:
    v = week[b].fillna(0).to_numpy()
    up, down = np.clip(v, 0, None), np.clip(v, None, 0)
    top.fill_between(
        week.index, pos, pos + up, color=COLORS[b], lw=0, alpha=0.85, step="post"
    )
    top.fill_between(
        week.index, neg, neg + down, color=COLORS[b], lw=0, alpha=0.85, step="post"
    )
    mids.append(
        (
            b,
            float(pos[-1] + up[-1] / 2) if up[-1] else float(neg[-1] + down[-1] / 2),
            float(v[-1]),
        )
    )
    pos, neg = pos + up, neg + down
top.plot(week.index, week.net, color=ps.TOKENS["text"], lw=0.8, drawstyle="steps-post")
top.axhline(0, color=ps.PALETTE[2], lw=0.8)
top.xaxis.set_major_locator(mdates.DayLocator(tz=CPH))
top.xaxis.set_major_formatter(mdates.DateFormatter("%-d %b", tz=CPH))

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
    color=P[1],
    label="At import limit",
)
bottom.bar(
    x + 0.2,
    [100 * s[1] for s in shares],
    width=0.4,
    color=P[3],
    label="At export limit",
)
bottom.set_xticks(x, [NAMES[b] for b in bt.BORDERS])
bottom.tick_params(axis="x", labelsize=6.5)
bottom.legend(loc="upper right", frameon=False, fontsize=7)

any_limit = ((year.n_limit_import + year.n_limit_export) > 0).mean()
ps.frame(
    fig,
    title=f"At least one DK1 border sat at its observed limit in {any_limit:.0%} of ISPs over the year",
    subtitle=(
        "(a) DK1 physical flow by border, 20-26 Oct 2026, Copenhagen time, + = import, stacked, "
        "with the net import as a line. (b) Share of ISPs each border sat at its observed limit, "
        "1 Oct 2025 - 28 Oct 2026: within 2 % of the border's largest flow in that direction over "
        "the past 28 days; an observed limit, not a rated capacity. First prints."
    ),
    units=["MW", "%"],
    cadence="quarter-hourly",
    source=f"{ATTRIBUTION} (ElectricityProdex5MinRealtime)",
    licence=LICENCE,
    asof="2026-10-28",  # the end of the 1 Oct 2025 - 28 Oct 2026 window
    xlabel=["Date, Copenhagen time (October 2026)", "Border"],
    ylabel=["Physical flow, ISP mean (MW, + = import)", "Share of ISPs (%)"],
    margins=(0.65, 1.15, 0.2, 0.5),
)
labels = [(NAMES[b].replace(" (Great Belt)", ""), y, COLORS[b]) for b, y, _ in mids]
labels.append(("Net import", float(week.net.iloc[-1]), ps.TOKENS["text"]))
dys = label_offsets(top, [y for _, y, _ in labels], gap_pt=9)
for (name, y, colour), dy in zip(labels, dys, strict=True):
    name_label(top, week.index[-1], y, name, color=colour, dy=dy)
ps.save(fig, HERE / "interconnectors", formats=("pdf", "png", "tex"))
print(f"ISPs with any border at its limit: {any_limit:.1%}")
