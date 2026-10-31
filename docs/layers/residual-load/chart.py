"""Layer #32's chart: residual_load.png beside this file.

    uv run --all-groups python docs/layers/residual-load/chart.py

Top: DK1 residual load, 20-26 Oct 2026 (the 01 notebook's week), with the
imbalance target for scale. Bottom: mean residual load by Copenhagen hour,
winter (Dec-Feb) against summer (Jun-Aug), from the first prints since
1 Oct 2025; each season's peak hour is read from the data, not assumed.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import psycopg

sys.path.insert(0, str(Path(__file__).parents[3] / "jobs"))
from _common import DB_URL

NAVY, BLUE, GREY, BAND = "#0F2A4A", "#1F5FBF", "#7D8996", "#DCE3EC"
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": BAND, "axes.axisbelow": True})  # fmt: skip
RL, SD = "energinet.dk1.residual_load_mw", "energinet.dk1.satisfied_demand"


def first_prints(conn, sid, frm, to):
    rows = conn.execute(
        "select distinct on (observed_for) observed_for, value from observation"
        " where series_id = %s and observed_for >= %s and observed_for < %s"
        " order by observed_for, published_at, observation_id",
        (sid, frm, to),
    ).fetchall()
    return pd.Series({t: float(v) for t, v in rows}).sort_index()


with psycopg.connect(DB_URL) as conn:
    rl = first_prints(
        conn, RL, datetime(2025, 10, 1, tzinfo=UTC), datetime(2026, 10, 29, tzinfo=UTC)
    )
    sd = first_prints(
        conn,
        SD,
        datetime(2026, 10, 19, 22, tzinfo=UTC),
        datetime(2026, 10, 26, 23, tzinfo=UTC),
    )
rl.index = rl.index.tz_convert("Europe/Copenhagen")
sd.index = sd.index.tz_convert("Europe/Copenhagen")
week = rl["2026-10-20":"2026-10-26"]

fig, (top, bottom) = plt.subplots(
    2, 1, figsize=(11, 6.5), gridspec_kw={"height_ratios": [3, 2]}
)
top.axhline(0, color=GREY, lw=0.8)
top.plot(
    week.index, week, color=NAVY, lw=1.2, label="residual load: demand − wind − solar"
)
top.plot(sd["2026-10-20":"2026-10-26"].index, sd["2026-10-20":"2026-10-26"], color=BLUE, lw=0.8,
         alpha=0.7, label="balancing energy activated (the forecast target)")  # fmt: skip
top.set_ylabel("MW, 15-minute mean")
top.set_title("Western Denmark: demand left after wind and solar, 20–26 Oct 2026", loc="left")
top.xaxis.set_major_formatter(mdates.DateFormatter("%-d %b", tz="Europe/Copenhagen"))
top.legend(loc="upper left", frameon=False, fontsize=9)

summary = []
for label, months, color in (
    ("winter (Dec–Feb)", (12, 1, 2), NAVY),
    ("summer (Jun–Aug)", (6, 7, 8), BLUE),
):
    s = rl[rl.index.month.isin(months)]
    prof = s.groupby(s.index.hour).mean()
    peak = int(prof.idxmax())
    bottom.plot(
        prof.index, prof, color=color, lw=1.5, label=f"{label}: peak {peak:02d}:00"
    )
    bottom.axvline(peak, color=color, lw=0.8, ls=":")
    summary.append(
        f"{label}: mean {s.mean():.0f} MW, peak hour {peak:02d}:00, min {prof.min():.0f} MW at {int(prof.idxmin()):02d}:00"
    )
bottom.axhline(0, color=GREY, lw=0.8)
bottom.set_xlabel("hour of the day, Copenhagen")
bottom.set_ylabel("MW, average")
bottom.set_xticks(range(0, 24, 3))
bottom.legend(loc="upper left", frameon=False, fontsize=9)
fig.text(0.01, -0.02, "Source: Energinet (CC BY 4.0), ElectricityProdex5MinRealtime, first prints. "
         "Measured as thermal plants plus net imports across six borders.",
         fontsize=8, color=GREY)  # fmt: skip
fig.tight_layout()
fig.savefig(Path(__file__).with_name("residual_load.png"), dpi=150, bbox_inches="tight")
print("\n".join(summary))
