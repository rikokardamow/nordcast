"""Experiment: is persistence a real bar for the direction call?

    uv run --all-groups python docs/experiments/direction-bar/run.py

notes/preregistration.md tests lightgbm_v1's direction by Brier against
persistence. Persistence's direction "probabilities" are one-hot (1 on its
call), so any calibrated model may clear that bar without knowing anything.
The live record also freezes direction_climatology (each direction's share
at the target's Copenhagen hour over the last 28 days, add-one smoothed).
This compares the three out of sample on the replay's 2026 rounds:
  persistence   one-hot on the last known direction (pers_dir)
  climatology   by Copenhagen hour, from first-print labels of the 28 days
                before the target's day (a day staler than live: conservative)
  v1            LightGBM v1's calibrated probabilities, refit before each
                round as in docs/experiments/v2-layer-features
Brier per ISP, accuracy of the argmax, and the day-block gain v1 vs each.
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


v2 = _load("v2", HERE.parent / "v2-layer-features" / "run.py")
rl_bt, replay, model = v2.rl_bt, v2.replay, v2.model
C = list(model.CLASSES)  # down, none, up


def brier(probs, y_dir):
    onehot = np.array([[c == d for c in C] for d in y_dir], dtype=float)
    return pd.Series(((probs - onehot) ** 2).sum(axis=1), index=y_dir.index)


def climatology(rows, every):
    """P(class) by Copenhagen hour from the 28 days before each target's day."""
    local = every.target.dt.tz_convert(replay.CPH)
    lab = pd.DataFrame(
        {"day": local.dt.normalize(), "hour": local.dt.hour, "y": every.y_dir}
    )
    r_local = rows.target.dt.tz_convert(replay.CPH)
    out = np.zeros((len(rows), 3))
    for day, idx in rows.groupby(r_local.dt.normalize()).groups.items():
        past = lab[(lab.day < day) & (lab.day >= day - pd.Timedelta(days=28))]
        counts = (
            past.groupby(["hour", "y"])
            .size()
            .unstack(fill_value=0)
            .reindex(columns=C, fill_value=0)
        )
        pos = rows.index.get_indexer(idx)
        for p, hour in zip(pos, r_local.loc[idx].dt.hour):
            c = counts.loc[hour].to_numpy() + 1 if hour in counts.index else np.ones(3)
            out[p] = c / c.sum()
    return out


def main():
    params = {
        int(k[1:]): v["params"]
        for k, v in json.loads(v2.MANIFEST.read_text())["models"].items()
    }
    out = []
    for h in (15, 30, 60):
        every = pd.read_parquet(f"data/training/h{h}.parquet").sort_values("target")
        for name in rl_bt.ROUNDS:
            start, end = replay.ROUNDS[name]
            before = every[every.target < start - replay.LABEL_DELAY]
            rows = every[(every.target >= start) & (every.target < end)]
            a = int(len(before) * 0.75)
            m = model._fit(h, params[h], before.iloc[:a], before.iloc[a:])
            pred = m.predict(rows)
            probs = {
                "persistence": np.array(
                    [[d == c for c in C] for d in rows.pers_dir], dtype=float
                ),
                "climatology": climatology(rows, every),
                "v1": pred[["p_down", "p_none", "p_up"]].to_numpy(),
            }
            loss = {k: brier(p, rows.y_dir) for k, p in probs.items()}
            row = {"h": h, "round": name, "n": len(rows)}
            for k, p in probs.items():
                row[f"brier_{k}"] = float(loss[k].mean())
                row[f"acc_{k}"] = float(
                    np.mean(np.array(C)[p.argmax(axis=1)] == rows.y_dir.to_numpy())
                )
            row["share_none"] = float((rows.y_dir == "none").mean())
            for bar in ("persistence", "climatology"):
                g = rl_bt.gain(rows, loss[bar], loss["v1"])
                row |= {f"v1_vs_{bar}_{k}": v for k, v in g.items()}
            out.append(row)
            print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()
                   if not k.endswith("_days")}, flush=True)  # fmt: skip
    pd.DataFrame(out).to_csv(HERE / "results.csv", index=False, float_format="%.4f")


if __name__ == "__main__":
    main()
