"""Builds 03_model.ipynb: LightGBM v1 against persistence on the last 20 %.

uv run --all-groups python notebooks/build_03_model.py
uv run --all-groups jupyter nbconvert --execute --inplace notebooks/03_model.ipynb
"""

from pathlib import Path

import nbformat as nbf

md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell

cells = [
    md(
        "# 03 – LightGBM v1 against persistence\n\n"
        "DK1 `SatisfiedDemand`, every ISP of the last 20 % of the window from 1 Oct 2025, "
        "per horizon. The models here were fitted on the first 60 % and calibrated on the "
        "next 20 %. **The hyperparameters were chosen on this same 20 %**, so the model's "
        "rows are optimistic by that choice. Every input is an estimated vintage: this is "
        "not the record. The replay (step 5) and the live record are the honest tests."
    ),
    code(
        """import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from nordcast import model
from nordcast import paper_style as ps
from nordcast.figure_utils import ATTRIBUTION, LICENCE, name_label

D, M = Path("../data/training"), Path("../data/models")
manifest = json.loads((M / "manifest-lightgbm-v1.json").read_text())
rows, preds = [], {}
for h in (15, 30, 60):
    df = pd.read_parquet(D / f"h{h}.parquet")
    _, _, val = model.split(df)
    m = pickle.loads((M / f"holdout-lightgbm-v1-h{h}.pkl").read_bytes())
    pred = m.predict(val)
    preds[h] = (val, pred, m)
    rows.append({"h": h, "method": "lightgbm-v1", **model.score_frame(val, pred)})
    rows.append({"h": h, "method": "persistence", **model.score_frame(val, model.persistence_frame(val))})
    # direction only: the fit period's class shares as constant probabilities
    fit, _, _ = model.split(df)
    shares = fit.y_dir.value_counts(normalize=True)
    const = pd.DataFrame({"q10": np.nan, "q50": np.nan, "q90": np.nan,
                          **{f"p_{c}": shares.get(c, 0.0) for c in model.CLASSES}}, index=val.index)
    r = model.score_frame(val, const)
    rows.append({"h": h, "method": "constant shares (direction)",
                 **{k: (r[k] if k in ("n", "direction_acc", "brier", "pnl_eur") else np.nan) for k in r}})
card = pd.DataFrame(rows).set_index(["h", "method"])
print(f"validation: {val.target.min():%d %b %Y} – {val.target.max():%d %b %Y}, {len(val)} ISPs per horizon")
card.round({"mae": 1, "pinball": 1, "coverage": 3, "direction_acc": 3, "brier": 3, "pnl_eur": 0})"""
    ),
    md(
        "MAE and pinball (mean over q10/q50/q90) in MW. Coverage: share of first prints inside "
        "q10–q90, target 0.80. Brier over three classes; persistence puts all its weight on "
        "the last known direction. P&L: 10 MW left open in the called direction for each ISP, "
        "settled at the first-print imbalance price against day-ahead, EUR summed over the "
        "period (no costs, no limits, a translation of the call and not a strategy). "
        "Persistence's one-hot direction makes its Brier score harsh, so the fair bar for "
        "direction is the constant-shares row: the fit period's class frequencies."
    ),
    code(
        """skill = pd.DataFrame({
    h: {
        "pinball": 1 - card.loc[(h, "lightgbm-v1"), "pinball"] / card.loc[(h, "persistence"), "pinball"],
        "mae": 1 - card.loc[(h, "lightgbm-v1"), "mae"] / card.loc[(h, "persistence"), "mae"],
        "brier vs persistence": 1 - card.loc[(h, "lightgbm-v1"), "brier"] / card.loc[(h, "persistence"), "brier"],
        "brier vs constant shares": 1 - card.loc[(h, "lightgbm-v1"), "brier"]
        / card.loc[(h, "constant shares (direction)"), "brier"],
    }
    for h in (15, 30, 60)
}).T
skill.round(3)  # skill vs persistence: 0.10 = 10 % lower loss"""
    ),
    md("## Interval: raw quantiles against the conformal band"),
    code(
        """pd.DataFrame({
    h: {"raw q10-q90": float(np.mean((v.y >= p.q10_raw) & (v.y <= p.q90_raw))),
        "conformal (MAPIE)": float(np.mean((v.y >= p.q10) & (v.y <= p.q90)))}
    for h, (v, p, _) in preds.items()
}).T.round(3)"""
    ),
    md("## Direction calibration, 15 min"),
    code(
        """val, pred, _ = preds[15]
fig, axes = ps.figure(width=ps.COLUMN)
ax = axes[0][0]
curves, over = [], []
for cls, colour, ls in (("up", ps.PALETTE[1], "-"), ("down", ps.PALETTE[0], "--"), ("none", ps.PALETTE[2], ":")):
    p = pred[f"p_{cls}"]
    bins = pd.cut(p, np.linspace(0, 1, 11), include_lowest=True)
    obs = (val.y_dir == cls).groupby(bins, observed=True).mean()
    mid = p.groupby(bins, observed=True).mean()
    if cls != "none":
        mask = (mid >= 0.2) & (mid <= 0.7)
        over += list((mid - obs)[mask])
    ax.plot(mid, obs, marker="o", ls=ls, color=colour, ms=3)
    curves.append((cls, colour, float(mid.iloc[-1]), float(obs.iloc[-1])))
ax.plot([0, 1], [0, 1], color=ps.TOKENS["text_muted"], lw=0.7)
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ps.frame(
    fig,
    title=(
        f"At 15 min the up and down probabilities between 0.2 and 0.7 overstate the observed "
        f"frequency by {100 * np.mean(over):.0f} percentage points on average"
    ),
    subtitle="LightGBM v1 hold-out model; ten equal-width probability bins per class; the diagonal is perfect calibration; the top bins hold few ISPs. Estimated vintages, not the record.",
    units="probability",
    source=f"{ATTRIBUTION}; data/training/h15.parquet, models/holdout-lightgbm-v1-h15.pkl",
    licence=LICENCE,
    asof=f"{val.target.max():%Y-%m-%d}",
    xlabel="Predicted probability (0 to 1)",
    ylabel="Observed frequency (0 to 1)",
    margins=(0.6, 0.55, 0.2, 0.5),
)
for cls, colour, x_end, y_end in curves:
    name_label(ax, x_end, y_end, cls, color=colour)
ps.show(fig)
ps.save(fig, "03_calibration", formats=("pdf", "png", "tex"))"""
    ),
    md("## What the 15-minute volume model leans on"),
    code(
        """_, _, m = preds[15]
imp = pd.Series(m.quantile[0.5].booster_.feature_importance("gain"), index=m.feature_names)
(imp / imp.sum()).sort_values(ascending=False).head(12).round(3)"""
    ),
    md("## Settings chosen and artefacts"),
    code("""pd.DataFrame({h: v["params"] for h, v in manifest["models"].items()}).T"""),
]

nb = nbf.v4.new_notebook(cells=cells)
nb.metadata["kernelspec"] = {
    "name": "python3",
    "display_name": "Python 3",
    "language": "python",
}
Path(__file__).with_name("03_model.ipynb").write_text(nbf.writes(nb))
