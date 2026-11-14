"""Layer #32's chart: residual_load (.pdf, .png, .tex) beside this file.

    uv run --all-groups python docs/layers/residual-load/chart.py

Top: DK1 residual load, 20-26 Oct 2026 (the 01 notebook's week), with the
imbalance target for scale. Bottom: mean residual load by Copenhagen hour,
winter (Dec-Feb) against summer (Jun-Aug), from the first prints since
1 Oct 2025; each season's peak hour is read from the data, not assumed.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

import matplotlib.dates as mdates
import pandas as pd
import psycopg

from nordcast import paper_style as ps
from nordcast.figure_utils import ATTRIBUTION, LICENCE, label_offsets

sys.path.insert(0, str(Path(__file__).parents[3] / "jobs"))
from _common import DB_URL

NAVY, BLUE, GREY = ps.PALETTE[0], ps.PALETTE[1], ps.PALETTE[2]
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

fig, axes = ps.figure(2, 1, height_ratios=[3, 2], sharex=False)
top, bottom = axes[0][0], axes[1][0]
top.axhline(0, color=GREY, lw=0.8)
top.plot(week.index, week, color=NAVY, lw=1.0)
sd_week = sd["2026-10-20":"2026-10-26"]
top.plot(sd_week.index, sd_week, color=BLUE, lw=0.7, alpha=0.8)
top.xaxis.set_major_locator(mdates.DayLocator(tz="Europe/Copenhagen"))
top.xaxis.set_major_formatter(mdates.DateFormatter("%-d %b", tz="Europe/Copenhagen"))

summary, profiles = [], []
for label, months, color, ls in (
    ("winter (Dec–Feb)", (12, 1, 2), NAVY, "-"),
    ("summer (Jun–Aug)", (6, 7, 8), BLUE, "--"),
):
    s = rl[rl.index.month.isin(months)]
    prof = s.groupby(s.index.hour).mean()
    peak = int(prof.idxmax())
    bottom.plot(prof.index, prof, color=color, ls=ls, lw=1.2)
    bottom.axvline(peak, color=color, lw=0.7, ls=":")
    profiles.append((label.split(" ")[0].capitalize(), peak, prof, color))
    summary.append(
        f"{label}: mean {s.mean():.0f} MW, peak hour {peak:02d}:00, min {prof.min():.0f} MW at {int(prof.idxmin()):02d}:00"
    )
bottom.axhline(0, color=GREY, lw=0.8)
bottom.set_xticks(range(0, 24, 3))
winter_peak, summer_peak = profiles[0][1], profiles[1][1]
ps.frame(
    fig,
    title=(
        f"DK1 residual load peaks at {winter_peak:02d}:00 in winter and {summer_peak:02d}:00 in summer"
    ),
    subtitle=(
        "(a) DK1 residual load, 20-26 Oct 2026, with the imbalance target (SatisfiedDemand) for scale, "
        "Copenhagen time. (b) Mean residual load by Copenhagen hour, winter (Dec-Feb) against "
        "summer (Jun-Aug), from the first prints since 1 Oct 2025; each season's peak hour (dotted) "
        "is read from the data, not assumed. Residual load = demand minus wind minus solar; "
        "thermal = plants <100 MW + 100 MW or larger; net import = six exchanges, + = import."
    ),
    units="MW",
    cadence="quarter-hourly",
    source=f"{ATTRIBUTION} (ElectricityProdex5MinRealtime, first prints)",
    licence=LICENCE,
    asof="2026-10-29",  # the first prints read run to 29 Oct 2026
    xlabel=["Date, Copenhagen time (October 2026)", "Hour of day, Copenhagen time"],
    ylabel=["Residual load, ISP mean (MW)", "Mean residual load (MW)"],
    margins=(0.65, 1.45, 0.2, 0.5),
)
ends = [(week.index[-1], float(week.iloc[-1]), "Residual load", NAVY),
        (sd_week.index[-1], float(sd_week.iloc[-1]), "SatisfiedDemand", BLUE)]  # fmt: skip
dys = label_offsets(top, [e[1] for e in ends], gap_pt=10)
for (xe, ye, name, colour), dy in zip(ends, dys, strict=True):
    top.annotate(name, (xe, ye), xytext=(6, dy), textcoords="offset points", va="center",
                 fontsize=7.5, color=colour, annotation_clip=False)  # fmt: skip
ends = [
    (23, float(p.iloc[-1]), f"{n}, peak {pk:02d}:00", c) for n, pk, p, c in profiles
]
dys = label_offsets(bottom, [e[1] for e in ends], gap_pt=10)
for (xe, ye, name, colour), dy in zip(ends, dys, strict=True):
    bottom.annotate(name, (xe, ye), xytext=(6, dy), textcoords="offset points", va="center",
                    fontsize=7.5, color=colour, annotation_clip=False)  # fmt: skip
ps.save(fig, Path(__file__).with_name("residual_load"), formats=("pdf", "png", "tex"))
print("\n".join(summary))
