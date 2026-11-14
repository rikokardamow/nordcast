"""Draws replay/mae_by_round (.pdf, .png, .tex) from replay/scorecard.csv.

    uv run --group reports python notebooks/build_02_replay.py

One line per method, from the round it entered, for the 15-minute horizon.
Reads nothing but the CSV. The title, units and source go to the .tex caption, not
the image (nordcast.paper_style, docs/FIGURES.md). The replay runs on estimated data vintages, so it
is a rehearsal, not the live record.
"""

import csv
from pathlib import Path

from nordcast import paper_style as ps
from nordcast.figure_utils import ATTRIBUTION, LICENCE, label_offsets

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "replay" / "scorecard.csv"
OUT = ROOT / "replay" / "mae_by_round"
HORIZON = "15"
ASOF = "2026-09-30"  # the last day of the last replay round (2026q3)

# method id in the CSV -> (short name for the end label, colour, line style)
METHODS = {
    "persistence": ("Persistence", ps.PALETTE[2], "-"),
    "persistence_ar1": ("AR(1)", ps.PALETTE[0], "-"),
    "linear_lags_calendar": ("Linear", ps.PALETTE[1], "-"),
    "seasonal_naive_day": ("Yesterday", ps.PALETTE[2], ":"),
    "seasonal_naive_week": ("Last week", ps.PALETTE[2], "--"),
}


def round_label(r):
    """'2026q1' -> 'Q1 2026'."""
    return f"Q{r[-1]} {r[:4]}"


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

    fig, axes = ps.figure()
    ax = axes[0][0]
    ends = []
    for method, (name, colour, style) in METHODS.items():
        pts = sorted((x[r], v) for r, v in series.get(method, {}).items())
        if not pts:
            continue
        xs, ys = zip(*pts, strict=True)
        ax.plot(xs, ys, color=colour, ls=style, marker="o", ms=3)
        ends.append((xs[-1], ys[-1], name, colour))
    ax.set_xticks(range(len(rounds)), [round_label(r) for r in rounds])
    ax.set_xlim(-0.3, len(rounds) - 0.7)
    ps.frame(
        fig,
        title=(
            f"Adding mean reversion to persistence cut the 15-minute error by "
            f"{min(gains):.0%} to {max(gains):.0%} in each replay round both ran"
        ),
        subtitle=(
            "Mean absolute error of the 15-minute call by replay round, each method from the "
            "round it entered. AR(1) is persistence plus mean reversion; Linear is a linear "
            "model on lags and calendar; Yesterday and Last week repeat the same quarter-hour "
            "of the day before and the week before. The replay runs on estimated data "
            "vintages and is not the live record."
        ),
        units="MW",
        cadence="quarterly",
        source=f"{ATTRIBUTION} (replay/scorecard.csv, h = 15 min)",
        licence=LICENCE,
        asof=ASOF,
        xlabel="Replay round (calendar quarter)",
        ylabel="Mean absolute error (MW)",
        margins=(0.6, 1.0, 0.2, 0.5),
    )
    dys = label_offsets(ax, [e[1] for e in ends], gap_pt=9)
    for (xe, ye, name, colour), dy in zip(ends, dys, strict=True):
        ps.end_label(ax, xe, ye, name, f"{ye:.0f} MW", color=colour, dy=dy)
    ps.save(fig, OUT, formats=("pdf", "png", "tex"))
    print(f"wrote {OUT.relative_to(ROOT)}.(pdf|png|tex)")


if __name__ == "__main__":
    main()
