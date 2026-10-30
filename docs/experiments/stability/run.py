"""Experiment: is any model's edge significant and stable, or one regime's luck?

    uv run --all-groups python docs/experiments/stability/run.py

The energy-analyst skill's section 18 asks for what the replay and the model
cards didn't report: a test of the loss differential, and its cumulative path.
On the replay's 2026 rounds, out of sample, per horizon:
  v1           LightGBM v1, refit before each round (as v2-layer-features)
  ar1          persistence_ar1, the replay's winner (data/layers, jobs/layer_calls.py)
  linear       lags and calendar, refit weekly (replay.linear_lags_calendar)
  persistence  the bar; climatology for direction (as direction-bar)
d = daily mean of loss(bar) - loss(method): positive favours the method.
dm_t: Diebold-Mariano, mean of d over its Newey-West error (7 lags).
trend: the fitted change in d from the first day to the last, with its HAC t.
clean_*: the same before 10 Aug 2026; v1's settings were chosen on 10 Aug - 27 Oct,
so only these days are free of that choice.
"""

import importlib.util
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

HERE = Path(__file__).parent
LAGS = 7
SETTINGS_CHOSEN_FROM = pd.Timestamp("2026-08-10")
NAVY, BLUE, GREY, RED = "#0F2A4A", "#1F5FBF", "#7D8996", "#C0392B"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bar = _load("bar", HERE.parent / "direction-bar" / "run.py")
model, replay, v2 = bar.model, bar.replay, bar.v2


def pinball(y, q10, q50, q90):
    per = [
        np.maximum(t * (y - q), (t - 1) * (y - q))
        for t, q in ((0.1, q10), (0.5, q50), (0.9, q90))
    ]
    return sum(per) / 3


def daily(d):
    day = d.index.tz_convert(replay.CPH).tz_localize(None).normalize()
    return d.groupby(day).mean()


def test(d):
    """Mean of daily d, DM t and p, and its trend across the sample (HAC)."""
    d = d.dropna()
    x = np.arange(len(d)) / (len(d) - 1)
    hac = {"maxlags": LAGS}
    level = sm.OLS(d.to_numpy(), np.ones(len(d))).fit(cov_type="HAC", cov_kwds=hac)
    slope = sm.OLS(d.to_numpy(), sm.add_constant(x)).fit(cov_type="HAC", cov_kwds=hac)
    return {
        "days": len(d),
        "mean_d": float(level.params[0]),
        "dm_t": float(level.tvalues[0]),
        "dm_p": float(2 * stats.norm.sf(abs(level.tvalues[0]))),
        "trend": float(slope.params[1]),
        "trend_t": float(slope.tvalues[1]),
    }


def losses(h, params):
    every = pd.read_parquet(f"data/training/h{h}.parquet").sort_values("target")
    calls = pd.read_parquet(f"data/layers/calls_h{h}.parquet").set_index("target")
    vol, brier = [], []
    for name in bar.rl_bt.ROUNDS:
        start, end = replay.ROUNDS[name]
        before = every[every.target < start - replay.LABEL_DELAY]
        rows = every[(every.target >= start) & (every.target < end)]
        a = int(len(before) * 0.75)
        pred = model._fit(h, params, before.iloc[:a], before.iloc[a:]).predict(rows)
        lin = replay.linear_lags_calendar(rows, None, {"all": every})
        c = calls.reindex(rows.target)
        y, idx = rows.y.to_numpy(), pd.DatetimeIndex(rows.target)
        vol.append(
            pd.DataFrame(
                {
                    "v1": pinball(y, pred.q10.to_numpy(), pred.q50.to_numpy(), pred.q90.to_numpy()),
                    "ar1": pinball(y, c.q10.to_numpy(), c.point.to_numpy(), c.q90.to_numpy()),
                    "linear": pinball(y, lin.q10.to_numpy(), lin.q50.to_numpy(), lin.q90.to_numpy()),
                    "persistence": pinball(y, rows.pers_q10.to_numpy(), rows.pers_point.to_numpy(), rows.pers_q90.to_numpy()),
                },
                index=idx,
            )
        )  # fmt: skip
        p = pred[["p_down", "p_none", "p_up"]].to_numpy()
        brier.append(
            pd.DataFrame(
                {
                    "v1": bar.brier(p, rows.y_dir).to_numpy(),
                    "climatology": bar.brier(bar.climatology(rows, every), rows.y_dir).to_numpy(),
                },
                index=idx,
            )
        )  # fmt: skip
    return pd.concat(vol), pd.concat(brier)


PAIRS = [
    ("pinball", "v1", "persistence"),
    ("pinball", "ar1", "persistence"),
    ("pinball", "v1", "ar1"),
    ("pinball", "linear", "ar1"),
    ("brier", "v1", "climatology"),
]


def main():
    manifest = json.loads(v2.MANIFEST.read_text())["models"]
    out, paths = [], {}
    for h in (15, 30, 60):
        vol, brier = losses(h, manifest[f"h{h}"]["params"])
        for loss, method, base in PAIRS:
            frame = vol if loss == "pinball" else brier
            d = daily((frame[base] - frame[method]).dropna())
            paths[(h, loss, method, base)] = d
            clean = test(d[d.index < SETTINGS_CHOSEN_FROM])
            out.append({"h": h, "loss": loss, "method": method, "bar": base, **test(d),
                        "clean_days": clean["days"], "clean_mean_d": clean["mean_d"],
                        "clean_dm_t": clean["dm_t"]})  # fmt: skip
            print(out[-1], flush=True)
    pd.DataFrame(out).to_csv(HERE / "results.csv", index=False, float_format="%.4f")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    for h, colour, ls in ((15, NAVY, "-"), (30, BLUE, "-"), (60, GREY, "--")):
        d = paths[(h, "pinball", "v1", "ar1")]
        axes[0].plot(d.index, d.cumsum(), color=colour, ls=ls, lw=1.3, label=f"{h} min")
        d = paths[(h, "brier", "v1", "climatology")]
        axes[1].plot(d.index, d.cumsum(), color=colour, ls=ls, lw=1.3, label=f"{h} min")
    axes[0].set_title("Volume: LightGBM v1 keeps gaining on AR(1)", loc="left")
    axes[0].set_ylabel("cumulative daily pinball gain, MW")
    axes[1].set_title(
        "Direction: its gain on hour-of-day climatology is fading", loc="left"
    )
    axes[1].set_ylabel("cumulative daily Brier gain")
    for ax in axes:
        ax.axhline(0, color=GREY, lw=0.6)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(frameon=False)
        ax.tick_params(axis="x", rotation=30)
    fig.text(0.01, 0.005, "A rising line means LightGBM is gaining. Replay on estimated vintages, 1 Jan - 30 Sep 2026, not the record. Data: Energinet, Energi Data Service.", fontsize=8, color=GREY)  # fmt: skip
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(HERE / "stability.png", dpi=150)


if __name__ == "__main__":
    main()
