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

URL = os.environ.get(
    "NORDCAST_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:44332/postgres"
)
CPH = ZoneInfo("Europe/Copenhagen")
START, END = datetime(2026, 10, 20, tzinfo=CPH), datetime(2026, 10, 27, tzinfo=CPH)

# Chart colours from energy-forecasting's design tokens (light mode).
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

SERIES = [
    "satisfied_demand",
    "afrr_up_mw",
    "afrr_down_mw",
    "mfrr_up_mw",
    "mfrr_down_mw",
    "wind_onshore_mw",
    "wind_onshore_fc_da_mw",
    "wind_onshore_fc_1h_mw",
    "wind_offshore_mw",
    "wind_offshore_fc_da_mw",
]
with psycopg.connect(URL) as conn:
    frames = {
        s: pd.Series(
            dict(
                conn.execute(
                    "select * from history_asof(%s, %s, %s, now())",
                    (f"energinet.dk1.{s}", START, END),
                ).fetchall()
            ),
            dtype=float,
        )
        for s in SERIES
    }
    scores = pd.DataFrame(
        conn.execute(
            "select f.method, f.horizon_min, s.abs_error, s.pinball_q10, s.pinball_q50,"
            " s.pinball_q90, s.covered, s.direction_hit, s.brier"
            " from score s join forecast f using (forecast_id)"
        ).fetchall(),
        columns=[
            "method",
            "horizon_min",
            "abs_error",
            "pinball_q10",
            "pinball_q50",
            "pinball_q90",
            "covered",
            "direction_hit",
            "brier",
        ],
    )
df = pd.DataFrame(frames).tz_convert(CPH)
df.describe().round(1)"""
    ),
    code(
        '''import itertools

import matplotlib.dates as mdates

TEXT, MUTED = "#0B1F3A", "#5B6878"
plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "axes.edgecolor": BAND,
        "axes.labelcolor": MUTED,
        "axes.grid.axis": "y",
        "grid.linewidth": 0.5,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "text.color": TEXT,
        "font.size": 9,
    }
)

q = df.resample("15min").mean()  # the target is settled per quarter-hour
target = q.satisfied_demand
n = int(target.notna().sum())
up, down = int((target > 0).sum()), int((target < 0).sum())
afrr = q.afrr_up_mw + q.afrr_down_mw
on_err = q.wind_onshore_mw - q.wind_onshore_fc_da_mw
off_err = q.wind_offshore_mw - q.wind_offshore_fc_da_mw
off_adj = off_err - off_err.mean()


def end_labels(ax, items, gap_frac=0.11):
    """Label each series at its right edge, nudged apart so none overlap."""
    lo, hi = ax.get_ylim()
    gap = (hi - lo) * gap_frac
    ys = [float(s.dropna().iloc[-1]) for s, _ in items]
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    placed = list(ys)
    for a, b in itertools.pairwise(order):
        if placed[b] - placed[a] < gap:
            placed[b] = placed[a] + gap
    for (s, text), y in zip(items, placed, strict=True):
        ax.annotate(
            text,
            (END, y),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            fontsize=8.5,
            color=TEXT,
            annotation_clip=False,
        )


fig, (top, bottom) = plt.subplots(
    2,
    1,
    figsize=(10, 6.2),
    sharex=True,
    gridspec_kw={"height_ratios": [3, 2], "hspace": 0.25},
)
fig.subplots_adjust(left=0.06, right=0.8, top=0.86, bottom=0.1)
fig.text(
    0.01,
    0.97,
    "DK1 system imbalance and wind forecast error, 20 to 26 October 2026",
    ha="left",
    va="top",
    fontsize=12,
    fontweight="bold",
    color=TEXT,
)
fig.text(
    0.01,
    0.925,
    f"MW per quarter-hour. Up-regulation was needed in {up / n:.0%} of "
    f"quarter-hours, down-regulation in {down / n:.0%}.",
    ha="left",
    va="top",
    fontsize=9.5,
    color=MUTED,
)

top.plot(target.index, target, color=NAVY, lw=1.0)
top.plot(afrr.index, afrr, color=BLUE, lw=0.8)
top.axhline(0, color=GREY, lw=0.5)
top.set_ylabel("MW, positive = up-regulation")
top.set_xlim(START, END)
end_labels(
    top,
    [
        (target, "balancing energy activated\\n(the forecast target)"),
        (afrr, "automatic reserve (aFRR)"),
    ],
)

bottom.plot(on_err.index, on_err, color=NAVY, lw=0.9)
bottom.plot(off_adj.index, off_adj, color=GREY, lw=0.9)
bottom.axhline(0, color=GREY, lw=0.5)
bottom.set_ylabel("MW, actual minus forecast")
bottom.set_xlim(START, END)
end_labels(
    bottom,
    [
        (on_err, "onshore wind"),
        (off_adj, f"offshore wind, less its\\nweekly mean of {off_err.mean():+.0f} MW"),
    ],
)

bottom.xaxis.set_major_locator(mdates.DayLocator(tz=CPH))
bottom.xaxis.set_major_formatter(mdates.DateFormatter("%-d %b", tz=CPH))
for ax in (top, bottom):
    ax.set_xlim(START, END)
    ax.tick_params(length=0)
fig.text(
    0.01,
    0.015,
    "Source: Energinet, Energi Data Service (ImbalancePrice, PowerSystemRightNow, "
    f"Forecasts_5Min), CC BY 4.0. Copenhagen time. Retrieved {datetime.now(CPH):%-d %b %Y}.",
    fontsize=8,
    color=MUTED,
)
fig.savefig("01_look.png", dpi=150)'''
    ),
    md(
        "Lower wind than forecast should need up-regulation: the correlation over "
        "the week, as a sanity check on the signs."
    ),
    code(
        """pd.DataFrame(
    {
        "onshore − day-ahead": [df.satisfied_demand.corr(on_err)],
        "onshore − 1 hour": [
            df.satisfied_demand.corr(df.wind_onshore_mw - df.wind_onshore_fc_1h_mw)
        ],
        "offshore − day-ahead": [df.satisfied_demand.corr(off_err)],
    },
    index=["corr with SatisfiedDemand"],
).round(3)"""
    ),
    md(
        "## Scorecard so far\n\n"
        "Every scored call, by method and horizon. MAE and pinball in MW; "
        "coverage is the share of first prints inside q10–q90 (target 80 %); "
        "Brier over three classes (0 is perfect, 2 a confident miss). "
        "`model` is v0, i.e. persistence, until a model earns the call."
    ),
    code(
        '''duckdb.sql("""
    select method, horizon_min as h, count(*) as n,
           round(avg(abs_error), 1) as mae,
           round(avg((pinball_q10 + pinball_q50 + pinball_q90) / 3), 1) as pinball,
           round(100 * avg(covered::int), 1) as coverage_pct,
           round(100 * avg(direction_hit::int), 1) as direction_pct,
           round(avg(brier), 3) as brier
    from scores group by all order by h, method
""").df()'''
    ),
]

nb = nbf.v4.new_notebook(cells=cells)
nb.metadata["kernelspec"] = {
    "name": "python3",
    "display_name": "Python 3",
    "language": "python",
}
Path(__file__).with_name("01_look.ipynb").write_text(nbf.writes(nb))
