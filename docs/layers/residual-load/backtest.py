"""Layer #32's test: does DK1 residual load, known at the freeze, explain the
ISP's imbalance beyond what the call already uses?

    uv run --all-groups python docs/layers/residual-load/backtest.py

Rows: data/training/h<h>.parquet (the model's training rows: first-print
labels, target lags and calendar as of isp - h - 5 min). Residual load is read
point-in-time from the observation table at the same asof (backfilled
vintages published at ISP end + 5 min, the feed's nominal lag).

Four linear models, each refit every Copenhagen Monday on rows whose ISP was
a day old (the replay's rung-4 procedure, replay.linear_lags_calendar):
  base      target lags + calendar (rung 4)
  base+rl   + residual-load features
  ren       base + the renewables' day-ahead errors already in lightgbm_v1
  ren+rl    + residual-load features
Scored out of sample on the replay's rounds 2026q1-q3, on absolute error of
the point. The gain is mean daily (loss without - loss with), with a
day-block bootstrap 90 % interval and a t statistic on daily means (a
Diebold-Mariano test robust to the intraday autocorrelation).
"""

import random
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

sys.path.insert(0, str(Path(__file__).parents[3] / "jobs"))
from _common import DB_URL

from nordcast import features, replay

RL = "energinet.dk1.residual_load_mw"
ISP = timedelta(minutes=15)
REN = ["wind_onshore_err_da_last", "wind_offshore_err_da_last", "solar_err_da_last"]
RLF = ["rl_last", "rl_ramp1h", "rl_dev_week"]
ROUNDS = ("2026q1", "2026q2", "2026q3")


def rl_features(pit, target, horizon):
    asof = features.freeze_time(target, horizon)
    recent = pit.history(RL, asof - timedelta(hours=2), asof, asof)
    if not recent:
        return dict.fromkeys(RLF)
    last = max(recent)
    v = recent[last]
    before = recent.get(last - 4 * ISP)
    week = pit.value(RL, last - timedelta(days=7), asof)
    return {
        "rl_last": v,
        "rl_ramp1h": None if before is None else v - before,
        "rl_dev_week": None if week is None else v - week,
    }


def fit_predict(rows, every, cols):
    """replay.linear_lags_calendar's weekly refit, with `cols` added."""
    out = pd.Series(np.nan, index=rows.index)
    local = rows.target.dt.tz_convert(replay.CPH)
    weeks = (local - pd.to_timedelta(local.dt.day_of_week, unit="D")).dt.normalize()

    def design(d):
        x = replay._design(d)
        for c in cols:
            x[c] = d[c].astype(float)
        return x

    for week, idx in rows.groupby(weeks).groups.items():
        fit = every[every.target < week - replay.LABEL_DELAY]
        fx = design(fit)
        ok = fx.notna().all(axis=1)
        beta, *_ = np.linalg.lstsq(fx[ok].to_numpy(), fit.y[ok].to_numpy(), rcond=None)
        x = design(rows.loc[idx])
        out.loc[x.index] = x.to_numpy() @ beta
    return out


def gain(rows, err_without, err_with, draws=10_000, seed=20261029):
    d = (err_without.abs() - err_with.abs()).rename("d")
    day = rows.target.dt.tz_convert(replay.CPH).dt.date
    daily = d.groupby(day).mean().dropna().to_list()
    n = len(daily)
    mean = sum(daily) / n
    sd = float(np.std(daily, ddof=1))
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(daily, k=n)) / n for _ in range(draws))
    return {"gain_mw": mean, "lo": means[int(0.05 * draws)],
            "hi": means[int(0.95 * draws) - 1], "t": mean / (sd / n**0.5), "days": n}  # fmt: skip


def main():
    out = []
    with psycopg.connect(DB_URL) as conn:
        pit = features.load(
            conn,
            replay.ROUNDS["2025q4"][0] - timedelta(days=9),
            replay.ROUNDS["2026q3"][1],
            series=[RL],
        )
    for h in (15, 30, 60):
        every = pd.read_parquet(f"data/training/h{h}.parquet").sort_values("target")
        every = every.join(
            pd.DataFrame(
                [rl_features(pit, t, h) for t in every.target], index=every.index
            )
        )
        every = every.dropna(subset=RLF + REN + replay.LINEAR_LAGS)
        for name in ROUNDS:
            start, end = replay.ROUNDS[name]
            rows = every[(every.target >= start) & (every.target < end)]
            pred = {
                k: fit_predict(rows, every, cols)
                for k, cols in (
                    ("base", []),
                    ("base+rl", RLF),
                    ("ren", REN),
                    ("ren+rl", REN + RLF),
                )
            }
            err = {k: p - rows.y for k, p in pred.items()}
            row = {"h": h, "round": name, "n": len(rows)}
            row |= {f"mae_{k}": float(e.abs().mean()) for k, e in err.items()}
            for a, b in (("base", "base+rl"), ("ren", "ren+rl")):
                g = gain(rows, err[a], err[b])
                row |= {f"{b}_{k}": v for k, v in g.items()}
            out.append(row)
            print(row, flush=True)
    table = pd.DataFrame(out)
    path = Path(__file__).with_name("backtest.csv")
    table.to_csv(path, index=False, float_format="%.3f")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
