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
import pandas as pd
import psycopg

from nordcast import paper_style as ps
from nordcast.figure_utils import ATTRIBUTION, LICENCE, label_offsets, name_label

URL = os.environ.get(
    "NORDCAST_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:44332/postgres"
)
CPH = ZoneInfo("Europe/Copenhagen")
START, END = datetime(2026, 10, 20, tzinfo=CPH), datetime(2026, 10, 27, tzinfo=CPH)

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
        """import matplotlib.dates as mdates

q = df.resample("15min").mean()  # the target is settled per quarter-hour
target = q.satisfied_demand
n = int(target.notna().sum())
up, down = int((target > 0).sum()), int((target < 0).sum())
afrr = q.afrr_up_mw + q.afrr_down_mw
on_err = q.wind_onshore_mw - q.wind_onshore_fc_da_mw
off_err = q.wind_offshore_mw - q.wind_offshore_fc_da_mw
off_adj = off_err - off_err.mean()

NAVY, BLUE, GREY = ps.PALETTE[0], ps.PALETTE[1], ps.PALETTE[2]
fig, axes = ps.figure(2, 1, height_ratios=[3, 2])
top, bottom = axes[0][0], axes[1][0]
top.plot(target.index, target, color=NAVY, lw=0.8)
top.plot(afrr.index, afrr, color=BLUE, lw=0.7)
top.axhline(0, color=GREY, lw=0.5)
bottom.plot(on_err.index, on_err, color=NAVY, lw=0.8)
bottom.plot(off_adj.index, off_adj, color=GREY, lw=0.8)
bottom.axhline(0, color=GREY, lw=0.5)
bottom.xaxis.set_major_locator(mdates.DayLocator(tz=CPH))
bottom.xaxis.set_major_formatter(mdates.DateFormatter("%-d %b", tz=CPH))
for ax in (top, bottom):
    ax.set_xlim(START, END)
ps.frame(
    fig,
    title=(
        f"Up-regulation was needed in {up / n:.0%} of quarter-hours and down-regulation in "
        f"{down / n:.0%} in DK1, 20 to 26 October 2026"
    ),
    subtitle=(
        "(a) Balancing energy Energinet activated to cover the system imbalance (the forecast "
        "target, positive = up-regulation), with the automatic reserve (aFRR). (b) Wind "
        "production minus Energinet's day-ahead forecast, onshore and offshore apart; offshore "
        f"runs a level above its forecast and is shown less its weekly mean of {off_err.mean():+.0f} MW. "
        "Quarter-hour means, Copenhagen time."
    ),
    units="MW",
    cadence="quarter-hourly",
    source=f"{ATTRIBUTION} (ImbalancePrice, PowerSystemRightNow, Forecasts_5Min)",
    licence=LICENCE,
    asof="2026-10-31",  # the newest vintage in the database when drawn
    xlabel="Date, Copenhagen time (2026)",
    ylabel=["Activated balancing energy (MW, + = up)", "Actual minus forecast (MW)"],
    margins=(0.65, 1.25, 0.2, 0.5),
)
for ax, items in (
    (top, [(target, "Balancing energy\\nactivated (target)", NAVY), (afrr, "aFRR", BLUE)]),
    (bottom, [(on_err, "Onshore wind", NAVY), (off_adj, "Offshore wind,\\nless weekly mean", GREY)]),
):
    ends = [(s.dropna().index[-1], float(s.dropna().iloc[-1])) for s, _, _ in items]
    dys = label_offsets(ax, [y for _, y in ends], gap_pt=16)
    for (s, text, colour), (x, y), dy in zip(items, ends, dys, strict=True):
        name_label(ax, x, y, text, color=colour, dy=dy)
ps.show(fig)
ps.save(fig, "01_look", formats=("pdf", "png", "tex"))"""
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
