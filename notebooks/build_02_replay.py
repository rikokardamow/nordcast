"""Draws replay/mae_by_round.png from replay/scorecard.csv.

    uv run --group reports python notebooks/build_02_replay.py

One line per method, from the round it entered, for the 15-minute horizon.
Reads nothing but the CSV. The replay runs on estimated data vintages, so it
is a rehearsal, not the live record.
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

TEXT, MUTED, BAND = "#0B1F3A", "#5B6878", "#DCE3EC"
NAVY, BLUE, GREY = "#0F2A4A", "#1F5FBF", "#7D8996"

# method id in the CSV -> (plain name, colour, line style)
METHODS = {
    "persistence": ("persistence (the last quarter-hour repeats)", GREY, "-"),
    "persistence_ar1": ("persistence plus mean reversion, AR(1)", NAVY, "-"),
    "linear_lags_calendar": ("linear model on lags and calendar", BLUE, "-"),
    "seasonal_naive_day": ("same quarter-hour yesterday", GREY, ":"),
    "seasonal_naive_week": ("same quarter-hour last week", GREY, "--"),
}

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": BAND,
        "axes.labelcolor": MUTED,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": BAND,
        "grid.linewidth": 0.5,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "text.color": TEXT,
        "font.size": 9,
        "lines.linewidth": 1.4,
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
    gains = [
        1 - series["persistence_ar1"][r] / series["persistence"][r]
        for r in rounds
        if r in series.get("persistence_ar1", {}) and r in series["persistence"]
    ]

    fig, ax = plt.subplots(figsize=(10, 4.8))
    fig.subplots_adjust(left=0.07, right=0.68, top=0.83, bottom=0.12)
    fig.text(
        0.01,
        0.97,
        "Replay: mean absolute error of the 15-minute call, by round",
        ha="left",
        va="top",
        fontsize=12,
        fontweight="bold",
    )
    fig.text(
        0.01,
        0.915,
        f"MW. Each method is shown from the round it entered. Adding mean "
        f"reversion to persistence cut the error by {min(gains):.0%} to {max(gains):.0%} "
        "in each round both ran.",
        ha="left",
        va="top",
        fontsize=9.5,
        color=MUTED,
    )

    ends = []
    for method, (name, colour, style) in METHODS.items():
        pts = sorted((x[r], v) for r, v in series.get(method, {}).items())
        if not pts:
            continue
        xs, ys = zip(*pts, strict=True)
        ax.plot(xs, ys, color=colour, ls=style, marker="o", ms=3.5)
        ends.append((ys[-1], f"{name}, {ys[-1]:.0f} MW"))
    for y_label, (_, text) in zip(
        spread([e[0] for e in ends], gap=6), ends, strict=True
    ):
        ax.text(
            len(rounds) - 1 + 0.08,
            y_label,
            text,
            va="center",
            color=TEXT,
            fontsize=8.5,
            clip_on=False,
        )

    ax.set_xticks(range(len(rounds)), [round_label(r) for r in rounds])
    ax.set_xlim(-0.3, len(rounds) - 0.7)
    ax.set_ylabel("MW")
    ax.tick_params(length=0)
    fig.text(
        0.01,
        0.02,
        "Source: Energinet, Energi Data Service, CC BY 4.0. Replay on estimated "
        f"data vintages, not the live record. {date.today():%-d %b %Y}.",
        fontsize=8,
        color=MUTED,
    )
    fig.savefig(OUT, dpi=150)
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
