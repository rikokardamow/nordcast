"""Experiment: can the direction call beat hour-of-day climatology by more?

    uv run --all-groups python docs/experiments/direction-v2/run.py

docs/experiments/direction-bar found v1's direction ahead of climatology by
0.01-0.03 Brier at 15-30 min and not at 60 min. Two cheap ideas, scored the
same way (out of sample on the replay's 2026 rounds, refit before each):
  blend   w * v1 + (1 - w) * climatology, w chosen on the calibration slice
          (the last 25 % before the round) from 0, 0.1, ..., 1
  stack   v1 refit with the three climatology probabilities as features
Bars: climatology and v1. Research only; lightgbm_v1 and the
pre-registration are untouched.
"""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


db = _load("db", HERE.parent / "direction-bar" / "run.py")
rl_bt, replay, model, v2 = db.rl_bt, db.replay, db.model, db.v2
CLIM = ["clim_p_down", "clim_p_none", "clim_p_up"]
WEIGHTS = np.round(np.arange(0, 1.01, 0.1), 1)


def gain(rows, without, with_):
    """rl_bt.gain, or zeros when the two losses are identical (blend w = 1)."""
    if np.allclose(without, with_):
        return {"gain_mw": 0.0, "lo": 0.0, "hi": 0.0}
    return rl_bt.gain(rows, without, with_)


def probs(m, rows):
    return m.predict(rows)[["p_down", "p_none", "p_up"]].to_numpy()


def main():
    params = {
        int(k[1:]): v["params"]
        for k, v in json.loads(v2.MANIFEST.read_text())["models"].items()
    }
    out = []
    for h in (15, 30, 60):
        every = (
            pd.read_parquet(f"data/training/h{h}.parquet")
            .sort_values("target")
            .reset_index(drop=True)
        )
        clim = db.climatology(
            every, every
        )  # each row from the 28 days before its own day
        every[CLIM] = clim
        for name in rl_bt.ROUNDS:
            start, end = replay.ROUNDS[name]
            before = every[every.target < start - replay.LABEL_DELAY]
            rows = every[(every.target >= start) & (every.target < end)]
            a = int(len(before) * 0.75)
            fit, cal = before.iloc[:a], before.iloc[a:]
            plain = [c for c in every.columns if c not in CLIM]
            v1 = model._fit(h, params[h], fit[plain], cal[plain])
            stack = model._fit(h, params[h], fit, cal)
            # the blend weight, on the calibration slice (v1's isotonic was fitted
            # there too, which flatters v1 a little and so pushes w up)
            cal_v1 = probs(v1, cal[plain])
            w = min(
                WEIGHTS,
                key=lambda w: db.brier(
                    w * cal_v1 + (1 - w) * cal[CLIM].to_numpy(), cal.y_dir
                ).mean(),
            )
            p = {
                "climatology": rows[CLIM].to_numpy(),
                "v1": probs(v1, rows[plain]),
                "stack": probs(stack, rows),
            }
            p["blend"] = w * p["v1"] + (1 - w) * p["climatology"]
            loss = {k: db.brier(v, rows.y_dir) for k, v in p.items()}
            row = {"h": h, "round": name, "w": float(w)}
            row |= {f"brier_{k}": float(v.mean()) for k, v in loss.items()}
            for k in ("v1", "blend", "stack"):
                g = gain(rows, loss["climatology"], loss[k])
                row |= {f"{k}_vs_clim_{s}": g[s] for s in ("gain_mw", "lo", "hi")}
            for k in ("blend", "stack"):
                g = gain(rows, loss["v1"], loss[k])
                row |= {f"{k}_vs_v1_{s}": g[s] for s in ("gain_mw", "lo", "hi")}
            out.append(row)
            print(
                {k: round(v, 4) if isinstance(v, float) else v for k, v in row.items()},
                flush=True,
            )
    pd.DataFrame(out).to_csv(HERE / "results.csv", index=False, float_format="%.4f")


if __name__ == "__main__":
    main()
