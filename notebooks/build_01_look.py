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
        "DK1, 20–26 Oct 2026 (Copenhagen days), newest vintage of each ISP. Top: the "
        "target, `SatisfiedDemand` (mFRR activated to cover the need, + up), with aFRR "
        "and mFRR requested beside it. Bottom: wind production minus Energinet's "
        "day-ahead and 1-hour forecasts, the error that drives most of the imbalance. "
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
          "wind_mw", "wind_fc_da_mw", "wind_fc_1h_mw"]
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
        """fig, (top, bottom) = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 2]})
top.plot(df.index, df.satisfied_demand, color=NAVY, lw=1.2, label="SatisfiedDemand (target)")
top.plot(df.index, df.afrr_up_mw + df.afrr_down_mw, color=BLUE, lw=0.9, label="aFRR, up + down")
top.plot(df.index, df.mfrr_up_mw - df.mfrr_down_mw, color=GREY, lw=0.9, ls="--",
         label="mFRR requested, up − down")
top.axhline(0, color=GREY, lw=0.6)
top.set_ylabel("MW (+ up-regulation)")
top.legend(loc="upper left", frameon=False, ncol=3)
top.set_title("DK1 balancing, 20–26 Oct 2026", loc="left")

bottom.plot(df.index, df.wind_mw - df.wind_fc_da_mw, color=BLUE, lw=0.9, label="wind − day-ahead forecast")
bottom.plot(df.index, df.wind_mw - df.wind_fc_1h_mw, color=GREY, lw=0.9, label="wind − 1-hour forecast")
bottom.axhline(0, color=GREY, lw=0.6)
bottom.set_ylabel("MW")
bottom.legend(loc="upper left", frameon=False, ncol=2)
fig.text(0.01, 0.005, "Data: Energinet, Energi Data Service. Copenhagen time.", fontsize=8, color=GREY)
fig.tight_layout()
fig.savefig("01_look.png", dpi=150, bbox_inches="tight")"""
    ),
    md(
        "Lower wind than forecast should need up-regulation: the correlation over "
        "the week, as a sanity check on the signs."
    ),
    code(
        """pd.DataFrame({
    "wind − day-ahead": [df.satisfied_demand.corr(df.wind_mw - df.wind_fc_da_mw)],
    "wind − 1 hour": [df.satisfied_demand.corr(df.wind_mw - df.wind_fc_1h_mw)],
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
