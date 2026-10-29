"""Experiment: do layers #31-#33's features help LightGBM, where the linear
tests (docs/layers/*/backtest.py) found nothing?

    uv run --all-groups python docs/experiments/v2-layer-features/run.py

Research only: lightgbm_v1 (the live challenger) and its pre-registration
are untouched. A v2 would need its own model card and pre-registration.

For each of the replay's 2026 rounds and each horizon, two LightGBM sets are
fitted with v1's own procedure (model._fit: quantile boosters + MAPIE band +
isotonic direction) and v1's chosen settings, on every row before the round
(boosters on the first 75 %, calibration on the last 25 %), and scored on the
round:
  v1       v1's features
  v1+lay   + residual load (3), interconnectors (4), day-ahead spreads (5)
Per-ISP losses: pinball (mean of q10/q50/q90) and Brier. Gain = mean daily
(loss v1 - loss v1+lay), day-block bootstrap 90 % interval, t on daily means.
v1's settings were chosen on v1's features, which favours v1 a little.
"""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

HERE = Path(__file__).parent
LAYERS = HERE.parents[1] / "layers"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pc = _load("pc_bt", LAYERS / "price-coupling" / "backtest.py")
ic, rl_bt, replay = pc.ic, pc.rl_bt, pc.replay
from nordcast import model

LAYER = ic.RLF + ic.ICF + pc.PCF
MANIFEST = HERE.parents[2] / "data" / "models" / "manifest-lightgbm-v1.json"


def per_isp(df, pred):
    pin = np.mean(
        [np.maximum(t * (df.y - pred[f"q{int(t * 100)}"]),
                    (t - 1) * (df.y - pred[f"q{int(t * 100)}"])) for t in model.QUANTILES],
        axis=0,
    )  # fmt: skip
    probs = pred[["p_down", "p_none", "p_up"]].to_numpy()
    onehot = np.array([[c == d for c in model.CLASSES] for d in df.y_dir], dtype=float)
    return pd.DataFrame(
        {"pinball": pin, "brier": ((probs - onehot) ** 2).sum(axis=1)}, index=df.index
    )


def main():
    params = {
        int(k[1:]): v["params"]
        for k, v in json.loads(MANIFEST.read_text())["models"].items()
    }
    spreads = pc.prices()
    with psycopg.connect(ic.DB_URL) as conn:
        frame = ic.isp_frame(conn)
    out = []
    for h in (15, 30, 60):
        every = pd.read_parquet(f"data/training/h{h}.parquet").sort_values("target")
        every = every.join(ic.known_at(frame, every.target, h))
        every = every.join(
            spreads.reindex(every.target.to_numpy()).set_axis(every.index)
        )
        for name in rl_bt.ROUNDS:
            start, end = replay.ROUNDS[name]
            before = every[every.target < start - replay.LABEL_DELAY]
            rows = every[(every.target >= start) & (every.target < end)]
            a = int(len(before) * 0.75)
            fit, cal = before.iloc[:a], before.iloc[a:]
            loss = {}
            for tag, drop in (("v1", LAYER), ("v1+lay", [])):
                cols = [c for c in every.columns if c not in drop]
                m = model._fit(h, params[h], fit[cols], cal[cols])
                pred = m.predict(rows[cols])
                loss[tag] = per_isp(rows, pred)
                s = model.score_frame(rows, pred)
                out.append({"h": h, "round": name, "model": tag, **s})
            row = {"h": h, "round": name, "model": "gain"}
            for metric in ("pinball", "brier"):
                g = rl_bt.gain(rows, loss["v1"][metric], loss["v1+lay"][metric])
                row |= {f"{metric}_{k}": v for k, v in g.items()}
            out.append(row)
            print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()},
                  flush=True)  # fmt: skip
    pd.DataFrame(out).to_csv(HERE / "results.csv", index=False, float_format="%.4f")


if __name__ == "__main__":
    main()
