"""Builds 01_look.ipynb: the week of 20-26 Oct 2026 and the scorecard so far.

Edit the cells here, then:
    uv run --group reports python notebooks/build_01_look.py
    uv run --group reports jupyter nbconvert --execute --inplace notebooks/01_look.ipynb
"""

from pathlib import Path

import nbformat as nbf

md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell

cells = [
    md(
        "# 01 – a first look\n\n"
        "DK1, 20–26 Oct 2026 (Copenhagen days), newest vintage of each quarter-hour. Top: the "
        "target, the balancing energy Energinet activated to cover the system imbalance "
        "(`SatisfiedDemand`, positive = up-regulation), with the automatic reserve (aFRR) "
        "beside it. Bottom: wind production minus Energinet's day-ahead forecast, onshore "
        "and offshore apart: the 5-min feed and the forecasts define offshore differently, "
        "so offshore runs a level above its forecast and is shown less its weekly mean. "
        "Then the live scorecard: every call frozen since the record started, against "
        "the first print."
    ),
    code(
        """import os
from datetime import datetime
from zoneinfo import ZoneInfo

import duckdb
import matplotlib.pyplot as plt
import pandas as pd
import psycopg

URL = os.environ.get("NORDCAST_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:44332/postgres")
CPH = ZoneInfo("Europe/Copenhagen")
START, END = datetime(2026, 10, 20, tzinfo=CPH), datetime(2026, 10, 27, tzinfo=CPH)

# Chart colours from energy-forecasting's design tokens (light mode).
NAVY, BLUE, GREY, BAND = "#0F2A4A", "#1F5FBF", "#7D8996", "#DCE3EC"
plt.rcParams.update({"figure.figsize": (10, 4), "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": BAND})

SERIES = ["satisfied_demand", "afrr_up_mw", "afrr_down_mw", "mfrr_up_mw", "mfrr_down_mw",
          "wind_onshore_mw", "wind_onshore_fc_da_mw", "wind_onshore_fc_1h_mw",
          "wind_offshore_mw", "wind_offshore_fc_da_mw"]
with psycopg.connect(URL) as conn:
    frames = {
        s: pd.Series(dict(conn.execute(
            "select * from history_asof(%s, %s, %s, now())", (f"energinet.dk1.{s}", START, END)
        ).fetchall()), dtype=float)
        for s in SERIES
    }
    scores = pd.DataFrame(conn.execute(
        "select f.method, f.horizon_min, s.abs_error, s.pinball_q10, s.pinball_q50,"
        " s.pinball_q90, s.covered, s.direction_hit, s.brier"
        " from score s join forecast f using (forecast_id)"
    ).fetchall(), columns=["method", "horizon_min", "abs_error", "pinball_q10", "pinball_q50",
                            "pinball_q90", "covered", "direction_hit", "brier"])
df = pd.DataFrame(frames).tz_convert(CPH)
df.describe().round(1)"""
    ),
    code(
        """from textwrap import fill

import matplotlib.dates as mdates

# House style: the title states the finding, the subtitle the units, one muted
# footer names the source. Series are named in the panel, not in a legend box.
TEXT, MUTED = "#0B1F3A", "#5B6878"
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Inter", "Helvetica Neue", "Helvetica", "DejaVu Sans"],
    "axes.edgecolor": BAND, "axes.labelcolor": MUTED, "axes.grid.axis": "y",
    "grid.linewidth": 0.6, "xtick.color": MUTED, "ytick.color": MUTED,
    "text.color": TEXT, "font.size": 10,
})

q = df.resample("15min").mean()  # the target is settled per quarter-hour
target = q.satisfied_demand
n = int(target.notna().sum())
up, down = int((target > 0).sum()), int((target < 0).sum())
afrr = q.afrr_up_mw + q.afrr_down_mw
on_err = q.wind_onshore_mw - q.wind_onshore_fc_da_mw
off_err = q.wind_offshore_mw - q.wind_offshore_fc_da_mw
off_adj = off_err - off_err.mean()

fig, (top, bottom) = plt.subplots(2, 1, figsize=(11, 7.2), sharex=True,
                                  gridspec_kw={"height_ratios": [3, 2], "hspace": 0.3})
fig.subplots_adjust(left=0.07, right=0.98, top=0.8, bottom=0.1)
fig.text(0.01, 0.975, f"DK1 needed up-regulation in {up / n:.0%} of quarter-hours, down-regulation "
         f"in {down / n:.0%} and neither in {1 - (up + down) / n:.0%}, 20–26 Oct 2026",
         ha="left", va="top", fontsize=14, fontweight="bold", color=TEXT)
fig.text(0.01, 0.93, fill(
    "Top: the forecast target, balancing energy activated to cover the system imbalance, "
    "MW per quarter-hour. Positive means the system was short and generation was turned "
    "up. Bottom: wind production minus Energinet's day-ahead forecast, MW. Offshore is "
    f"shown less its weekly mean ({off_err.mean():+.0f} MW), because the live feed and the "
    "forecast define it differently.", 150), ha="left", va="top", fontsize=10, color=MUTED,
    linespacing=1.4)

top.plot(target.index, target, color=NAVY, lw=1.1)
top.plot(afrr.index, afrr, color=BLUE, lw=0.9)
top.axhline(0, color=GREY, lw=0.6)
top.set_ylabel("MW")
top.text(0, 1.03, "Balancing energy activated (the target)", transform=top.transAxes,
         color=NAVY, fontsize=10, fontweight="bold")
top.text(0.5, 1.03, "Automatic reserve (aFRR), up plus down", transform=top.transAxes,
         color=BLUE, fontsize=10, fontweight="bold")

bottom.plot(on_err.index, on_err, color=BLUE, lw=1.0)
bottom.plot(off_adj.index, off_adj, color=GREY, lw=1.0)
bottom.axhline(0, color=GREY, lw=0.6)
bottom.set_ylabel("MW")
bottom.text(0, 1.05, "Onshore wind, actual minus day-ahead forecast", transform=bottom.transAxes,
            color=BLUE, fontsize=10, fontweight="bold")
bottom.text(0.5, 1.05, "Offshore wind, the same, less its mean", transform=bottom.transAxes,
            color=GREY, fontsize=10, fontweight="bold")

loc = mdates.DayLocator(tz=CPH)
bottom.xaxis.set_major_locator(loc)
bottom.xaxis.set_major_formatter(mdates.DateFormatter("%-d %b", tz=CPH))
for ax in (top, bottom):
    ax.set_xlim(START, END)
    ax.tick_params(length=0)
fig.text(0.01, 0.012, "Source: Energinet, Energi Data Service (ImbalancePrice, PowerSystemRightNow, "
         f"Forecasts_5Min) · CC BY 4.0 · Copenhagen time · As of {datetime.now(CPH):%Y-%m-%d}",
         fontsize=8.5, color=MUTED)
fig.savefig("01_look.png", dpi=150)"""
    ),
    md(
        "Lower wind than forecast should need up-regulation: the correlation over "
        "the week, as a sanity check on the signs."
    ),
    code(
        """pd.DataFrame({
    "onshore − day-ahead": [df.satisfied_demand.corr(on_err)],
    "onshore − 1 hour": [df.satisfied_demand.corr(df.wind_onshore_mw - df.wind_onshore_fc_1h_mw)],
    "offshore − day-ahead": [df.satisfied_demand.corr(off_err)],
}, index=["corr with SatisfiedDemand"]).round(3)"""
    ),
    md(
        "## Scorecard so far\n\n"
        "Every scored call, by method and horizon. MAE and pinball in MW; "
        "coverage is the share of first prints inside q10–q90 (target 80 %); "
        "Brier over three classes (0 is perfect, 2 a confident miss). "
        "`model` is v0, i.e. persistence, until a model earns the call."
    ),
    code(
        """duckdb.sql('''
    select method, horizon_min as h, count(*) as n,
           round(avg(abs_error), 1) as mae,
           round(avg((pinball_q10 + pinball_q50 + pinball_q90) / 3), 1) as pinball,
           round(100 * avg(covered::int), 1) as coverage_pct,
           round(100 * avg(direction_hit::int), 1) as direction_pct,
           round(avg(brier), 3) as brier
    from scores group by all order by h, method
''').df()"""
    ),
]

nb = nbf.v4.new_notebook(cells=cells)
nb.metadata["kernelspec"] = {
    "name": "python3",
    "display_name": "Python 3",
    "language": "python",
}
Path(__file__).with_name("01_look.ipynb").write_text(nbf.writes(nb))
