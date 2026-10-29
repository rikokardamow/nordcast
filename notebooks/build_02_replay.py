"""Draws replay/mae_by_round.png from replay/scorecard.csv.

    uv run --group reports python notebooks/build_02_replay.py

One line per method, from the round it entered, for the 15-minute horizon.
Reads nothing but the CSV. House style: the title states the finding and is
computed from the data, the subtitle gives the units, lines are labelled at
their ends, one muted footer names the source. The replay runs on estimated
data vintages, so it is a rehearsal, not the live record.
"""

import csv
import itertools
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "replay" / "scorecard.csv"
OUT = ROOT / "replay" / "mae_by_round.png"
HORIZON = "15"

# energy-forecasting's design tokens, light mode
TEXT, MUTED, BAND = "#0B1F3A", "#5B6878", "#DCE3EC"
NAVY, BLUE, GREY = "#0F2A4A", "#1F5FBF", "#7D8996"

# method id in the CSV -> (plain name, colour, line style)
METHODS = {
    "persistence": ("Persistence (the last quarter-hour repeats)", GREY, "-"),
    "persistence_ar1": ("Persistence plus mean reversion, AR(1)", NAVY, "-"),
    "linear_lags_calendar": ("Linear model on lags and calendar", BLUE, "-"),
    "seasonal_naive_day": ("Same quarter-hour yesterday", GREY, ":"),
    "seasonal_naive_week": ("Same quarter-hour last week", GREY, "--"),
}

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Inter", "Helvetica Neue", "Helvetica", "DejaVu Sans"],
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": BAND,
        "axes.labelcolor": MUTED,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": BAND,
        "grid.linewidth": 0.6,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "text.color": TEXT,
        "font.size": 10,
        "lines.linewidth": 2,
    }
)


def round_label(r):
    """'2026q1' -> 'Q1 2026'."""
    return f"Q{r[-1]} {r[:4]}"


def spread(values, gap):
    """Nudge label positions apart so none sit closer than `gap`."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = list(values)
    for a, b in itertools.pairwise(order):
        if out[b] - out[a] < gap:
            out[b] = out[a] + gap
    return out


def main():
    with SRC.open() as f:
        rows = [r for r in csv.DictReader(f) if r["h"] == HORIZON]
    rounds = sorted({r["round"] for r in rows})
    x = {r: i for i, r in enumerate(rounds)}
    series = {}
    for r in rows:
        series.setdefault(r["method"], {})[r["round"]] = float(r["mae"])

    # The finding: how much AR(1) improved on persistence in every round both ran.
    gains = [
        1 - series["persistence_ar1"][r] / series["persistence"][r]
        for r in rounds
        if r in series.get("persistence_ar1", {}) and r in series["persistence"]
    ]
    title = (
        f"Mean reversion on top of persistence cut the 15-minute error by "
        f"{min(gains):.0%} to {max(gains):.0%} in every replay round it ran"
    )

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.subplots_adjust(left=0.07, right=0.66, top=0.8, bottom=0.12)
    fig.text(0.01, 0.975, title, ha="left", va="top", fontsize=13, fontweight="bold")
    fig.text(
        0.01,
        0.9,
        "Mean absolute error of the call made 15 minutes before each "
        "quarter-hour, MW, by quarterly replay round. Each method is shown from "
        "the round it entered.",
        ha="left",
        va="top",
        fontsize=10,
        color=MUTED,
    )

    ends = []
    for method, (name, colour, style) in METHODS.items():
        pts = sorted((x[r], v) for r, v in series.get(method, {}).items())
        if not pts:
            continue
        xs, ys = zip(*pts)
        ax.plot(
            xs,
            ys,
            color=colour,
            ls=style,
            marker="o",
            ms=5,
            markerfacecolor="white",
            markeredgewidth=1.5,
        )
        ends.append((ys[-1], name, colour, f"{ys[-1]:.0f}"))

    for y_label, (y, name, colour, val) in zip(
        spread([e[0] for e in ends], gap=6), ends
    ):
        ax.text(
            len(rounds) - 1 + 0.08,
            y_label,
            f"{name}  ·  {val} MW",
            va="center",
            color=colour,
            fontsize=9.5,
            clip_on=False,
        )

    ax.set_xticks(range(len(rounds)), [round_label(r) for r in rounds])
    ax.set_xlim(-0.3, len(rounds) - 0.7)
    ax.set_ylabel("MW")
    ax.tick_params(length=0)
    fig.text(
        0.01,
        0.02,
        "Replay on estimated data vintages, not the live record · Source: "
        f"Energinet, Energi Data Service · CC BY 4.0 · As of {date.today():%Y-%m-%d}",
        fontsize=8.5,
        color=MUTED,
    )
    fig.savefig(OUT, dpi=150)
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
