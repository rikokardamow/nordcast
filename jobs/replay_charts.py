"""Draw a replay round's analysis charts: acf, profiles, distribution.

    uv run --all-groups python jobs/replay_charts.py                # every round
    uv run --all-groups python jobs/replay_charts.py 2026q1 2026q2  # some rounds

Each chart is written next to analysis.md as .pdf, .png and .tex (nordcast.paper_style).
This file only reads: one SELECT on the observation table for the target's first prints
before the round, nothing else. It never touches replay/scorecard.csv, diagnostics.md
or any other record. jobs/replay_round.py imports `stats` and `draw` from here, so the
round job and this script draw the same figures.
"""

import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg
from _common import DB_URL
from statsmodels.tsa.stattools import pacf

from nordcast import paper_style as ps
from nordcast import replay
from nordcast.baselines import TARGET
from nordcast.figure_utils import ATTRIBUTION, LICENCE

ROOT = Path(__file__).resolve().parents[1]
NAVY, BLUE = ps.PALETTE[0], ps.PALETTE[1]


def first_prints(conn, series_id, frm, to):
    rows = conn.execute(
        "select distinct on (observed_for) observed_for, value from observation"
        " where series_id = %s and observed_for >= %s and observed_for < %s"
        " order by observed_for, published_at, observation_id",
        (series_id, frm, to),
    ).fetchall()
    return pd.Series({t: float(v) for t, v in rows}).sort_index()


def stats(y):
    """The numbers behind the three charts and analysis.md, from the target's first prints."""
    yl = y.tz_convert(replay.CPH)
    return {
        "acf": [float(y.autocorr(k)) for k in range(1, 97)],
        "pac": pacf(y.to_numpy(), nlags=16),
        "hour": yl.groupby(yl.index.hour).agg(["mean", "std"]),
        "week": yl.groupby(yl.index.day_of_week).mean(),
    }


def _mw(v):
    """A whole number of MW with a true minus sign."""
    return f"{v:.0f}".replace("-", ps.MINUS)


def _frame(fig, name, start, title, subtitle, xlabel, ylabel, units="MW"):
    ps.frame(
        fig,
        title=title,
        subtitle=subtitle,
        units=units,
        cadence="quarter-hourly",
        source=f"{ATTRIBUTION} (observation table, first prints before the round)",
        licence=LICENCE,
        asof=f"{start:%Y-%m-%d}",
        xlabel=xlabel,
        ylabel=ylabel,
        margins=(0.6, 0.15, 0.2, 0.5),
    )
    fig.subplots_adjust(wspace=0.38)


def draw(name, y, st, start, out):
    """Write acf, profiles and distribution (.pdf .png .tex) for round `name` into `out`."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    acf, pac, hour, week = st["acf"], st["pac"], st["hour"], st["week"]
    scope = f"Round {name}; first prints of DK1 SatisfiedDemand before the round only."
    # acf and pacf
    fig, axes = ps.figure(1, 2, sharex=False, size=(ps.FULL, 2.9))
    axes[0][0].bar(range(1, 97), acf, color=NAVY, width=0.8)
    axes[0][1].bar(range(1, 17), pac[1:], color=BLUE, width=0.8)
    _frame(
        fig, name, start,
        f"The target's autocorrelation falls from {acf[0]:.2f} at lag 1 to {acf[95]:.2f} at one day",
        f"(a) Autocorrelation, lags 1-96 ISPs. (b) Partial autocorrelation, lags 1-16. {scope}",
        ["Lag (ISPs of 15 min)", "Lag (ISPs of 15 min)"],
        ["Autocorrelation (correlation)", "Partial autocorrelation (correlation)"],
        units="correlation",
    )  # fmt: skip
    ps.save(fig, out / "acf", formats=("pdf", "png", "tex"))
    # profiles
    fig, axes = ps.figure(1, 2, sharex=False, size=(ps.FULL, 2.9))
    axes[0][0].plot(hour.index, hour["mean"], color=NAVY)
    axes[0][0].fill_between(
        hour.index,
        hour["mean"] - hour["std"],
        hour["mean"] + hour["std"],
        color=ps.TOKENS["border"],
    )
    axes[0][1].bar(week.index, week, color=BLUE)
    _frame(
        fig, name, start,
        f"The target averages {_mw(hour['mean'].min())} MW at {hour['mean'].idxmin()}:00 and "
        f"{_mw(hour['mean'].max())} MW at {hour['mean'].idxmax()}:00 by Copenhagen hour",
        f"(a) Mean by Copenhagen hour, shaded one standard deviation either side. (b) Mean by weekday. {scope}",
        ["Hour of day, Copenhagen time", "Weekday (0 = Monday)"],
        ["Mean SatisfiedDemand (MW)", "Mean SatisfiedDemand (MW)"],
    )  # fmt: skip
    ps.save(fig, out / "profiles", formats=("pdf", "png", "tex"))
    # distribution
    fig, axes = ps.figure(sharex=False, size=(ps.COLUMN, 2.6), width=ps.COLUMN)
    axes[0][0].hist(y, bins=80, color=NAVY)
    ps.frame(
        fig,
        title=f"{np.mean(y > 0):.0%} of first prints are up-regulation and {np.mean(y < 0):.0%} down-regulation",
        subtitle=f"Histogram, 80 bins; mean {_mw(y.mean())} MW, median {_mw(y.median())} MW. {scope}",
        units="MW",
        cadence="quarter-hourly",
        source=f"{ATTRIBUTION} (observation table, first prints before the round)",
        licence=LICENCE,
        asof=f"{start:%Y-%m-%d}",
        xlabel="SatisfiedDemand (MW)",
        ylabel="ISPs (count)",
        margins=(0.65, 0.15, 0.2, 0.5),
    )
    ps.save(fig, out / "distribution", formats=("pdf", "png", "tex"))


def main(names):
    names = names or list(replay.ROUNDS)
    with psycopg.connect(DB_URL) as conn:  # read-only: one SELECT per round
        for name in names:
            start, _ = replay.ROUNDS[name]
            y = first_prints(conn, TARGET, start - timedelta(days=366), start)
            draw(name, y, stats(y), start, ROOT / "replay" / name / "analysis")
            print(
                f"drew replay/{name}/analysis/(acf|profiles|distribution).(pdf|png|tex)"
            )


if __name__ == "__main__":
    main(sys.argv[1:])
