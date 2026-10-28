"""Run one replay round: analyse, forecast what plan.md names, score, diagnose.

    uv run --all-groups python jobs/replay_round.py 2025q4

Refuses to run without replay/<round>/plan.md: the method is chosen and
written down before anything is forecast. Writes analysis/ (charts and
analysis.md, from data before the round only), scorecard.csv and
diagnostics.md into replay/<round>/, and its lines into replay/scorecard.csv.
The review is written afterwards, from these files alone.
"""

import re
import sys
from datetime import timedelta
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import psycopg
from _common import DB_URL

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from statsmodels.tsa.stattools import adfuller, pacf

from nordcast import freeze, replay
from nordcast.baselines import TARGET

NAVY, BLUE, GREY, BAND = "#0F2A4A", "#1F5FBF", "#7D8996", "#DCE3EC"
plt.rcParams.update({"figure.figsize": (8, 3.2), "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": BAND})  # fmt: skip

name = sys.argv[1]
out = Path("replay") / name
plan = out / "plan.md"
if not plan.exists():
    sys.exit(f"{plan} missing: write the plan before the round runs")
methods = re.findall(r"^- method: (\S+)", plan.read_text(), re.MULTILINE)
start, end = replay.ROUNDS[name]


def first_prints(conn, series_id, frm, to):
    rows = conn.execute(
        "select distinct on (observed_for) observed_for, value from observation"
        " where series_id = %s and observed_for >= %s and observed_for < %s"
        " order by observed_for, published_at, observation_id",
        (series_id, frm, to),
    ).fetchall()
    return pd.Series({t: float(v) for t, v in rows}).sort_index()


# 1. analyse: the target before the round only
(out / "analysis").mkdir(parents=True, exist_ok=True)
with psycopg.connect(DB_URL) as conn:
    y = first_prints(conn, TARGET, start - timedelta(days=366), start)
yl = y.tz_convert(replay.CPH)
notes = [
    f"# {name} – analysis\n",
    f"target first prints {y.index.min():%d %b %Y} – {y.index.max():%d %b %Y} utc, {len(y)} isps, before the round only.\n",
]
acf = [float(y.autocorr(k)) for k in range(1, 97)]
pac = pacf(y.to_numpy(), nlags=16)
fig, ax = plt.subplots(1, 2)
ax[0].bar(range(1, 97), acf, color=NAVY, width=0.8)
ax[0].set_title("acf, lags 1-96 isps", loc="left")
ax[1].bar(range(1, 17), pac[1:], color=BLUE, width=0.8)
ax[1].set_title("pacf, lags 1-16", loc="left")
fig.tight_layout()
fig.savefig(out / "analysis" / "acf.png", dpi=120)
plt.close(fig)
hour = yl.groupby(yl.index.hour).agg(["mean", "std"])
week = yl.groupby(yl.index.weekday).mean()
fig, ax = plt.subplots(1, 2)
ax[0].plot(hour.index, hour["mean"], color=NAVY)
ax[0].fill_between(
    hour.index, hour["mean"] - hour["std"], hour["mean"] + hour["std"], color=BAND
)
ax[0].set_title("by copenhagen hour, mean ± sd", loc="left")
ax[1].bar(week.index, week, color=BLUE)
ax[1].set_title("by weekday (0 = mon), mean", loc="left")
fig.tight_layout()
fig.savefig(out / "analysis" / "profiles.png", dpi=120)
plt.close(fig)
fig, ax = plt.subplots()
ax.hist(y, bins=80, color=NAVY)
ax.set_title("distribution (mw)", loc="left")
fig.tight_layout()
fig.savefig(out / "analysis" / "distribution.png", dpi=120)
plt.close(fig)
adf = adfuller(y.to_numpy(), maxlag=96, autolag=None)
notes += [
    f"- acf: lag 1 {acf[0]:.2f}, lag 4 {acf[3]:.2f}, lag 8 {acf[7]:.2f}, lag 96 (a day) {acf[95]:.2f}.",
    f"- pacf: lag 1 {pac[1]:.2f}, lag 2 {pac[2]:.2f}, lag 3 {pac[3]:.2f}.",
    f"- by hour: most negative at {hour['mean'].idxmin()}:00 ({hour['mean'].min():.0f} mw), most positive at {hour['mean'].idxmax()}:00 ({hour['mean'].max():.0f} mw); sd {hour['std'].min():.0f}-{hour['std'].max():.0f} mw.",
    f"- distribution: mean {y.mean():.0f}, median {y.median():.0f}, sd {y.std():.0f}, skew {y.skew():.2f}, 1 % / 99 % {y.quantile(0.01):.0f} / {y.quantile(0.99):.0f} mw; {np.mean(y == 0):.1%} exactly 0, {np.mean(y > 0):.1%} up, {np.mean(y < 0):.1%} down.",
    f"- stationarity: adf statistic {adf[0]:.1f} (1 % critical {adf[4]['1%']:.1f}), p {adf[1]:.3g}.",
]

# 2-4. forecast, score, diagnose, per horizon
lines, diag_md = [], [f"# {name} – diagnostics\n"]
for h in freeze.HORIZONS:
    df = pd.read_parquet(Path("data/training") / f"h{h}.parquet")
    rows, train = replay.round_rows(df, name), replay.training_rows(df, name)
    if h == freeze.HORIZONS[0]:
        tr = df[
            df.target < start
        ]  # correlations on the training window, when it exists
        base = tr if len(tr) > 500 else None
        if base is not None:
            corr = (
                base.drop(columns=["target", "y_dir", "pers_dir"])
                .corrwith(base.y)
                .drop("y")
                .sort_values()
            )
            notes.append(
                "- correlation with the target (training rows, 15 min): "
                + ", ".join(f"{k} {v:+.2f}" for k, v in corr.items() if abs(v) > 0.05)
            )
        else:
            notes.append(
                "- feature correlations: no training rows before this round (the clean window starts 1 oct 2025); the next rounds report them."
            )
    for m in methods:
        pred = replay.METHODS[m](rows, train)
        s = replay.scorecard(rows, pred)
        lines.append({"round": name, "method": m, "h": h, **s})
        d = replay.diagnostics(rows, pred)
        diag_md += [
            f"\n## {m}, {h} min\n",
            "mae by copenhagen hour (mw): "
            + ", ".join(f"{k}: {v:.0f}" for k, v in d["by_hour"].items()),
            "\nmae by onshore wind error at the freeze (mw, actual − day-ahead):\n",
            "```\n" + d["by_wind"].round(1).to_string() + "\n```",
            "\nresidual acf: "
            + ", ".join(f"lag {k} {v:.2f}" for k, v in d["acf"].items()),
            "\nten biggest misses:\n",
            "```\n"
            + d["worst"]
            .assign(
                target=lambda x: x.target.dt.tz_convert(replay.CPH).dt.strftime(
                    "%d %b %H:%M"
                )
            )
            .round(0)
            .to_string(index=False)
            + "\n```",
        ]

(out / "analysis" / "analysis.md").write_text("\n".join(notes) + "\n")
(out / "diagnostics.md").write_text("\n".join(diag_md) + "\n")
card = pd.DataFrame(lines)
card.to_csv(out / "scorecard.csv", index=False)
all_path = Path("replay/scorecard.csv")
old = pd.read_csv(all_path) if all_path.exists() else pd.DataFrame()
if len(old):
    old = old[old["round"] != name]
pd.concat([old, card]).to_csv(all_path, index=False)
print(card.round(3).to_string(index=False))
print("\n".join(notes))
