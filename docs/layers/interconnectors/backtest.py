"""Layer #33's test: do DK1's interconnector flows, known at the freeze, explain
the ISP's imbalance beyond the target's own history and residual load (#32)?

    uv run --all-groups python docs/layers/interconnectors/backtest.py

Rows: data/training/h<h>.parquet, as in layer #32's back-test. Flows and
residual load are first prints, visible at the freeze when the ISP ended at
least 5 min before it (the 5-min feed's nominal lag; each backfilled ISP has
one vintage, so this equals the history-as-of lookup and runs in seconds).

"At its limit": |flow| within 2 % of the largest flow in the same direction
over the 28 days up to that ISP. That is an observed limit, not a rated
capacity, which isn't published openly (RISK.md).

Features: n_limit_import, n_limit_export (borders at their limit), the 1-hour
ramp of net import, the 1-hour ramp of the German flow. Compared, with the
replay's weekly refit, out of sample on 2026q1-q3:
  rl       rung 4 + residual load (layer #32's three features)
  rl+ic    + the interconnector features
  base     rung 4
  base+ic  + the interconnector features
"""

import importlib.util
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd
import psycopg

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2] / "jobs"))
from _common import DB_URL

from nordcast import features, replay

spec = importlib.util.spec_from_file_location(
    "rl_bt", HERE.parent / "residual-load" / "backtest.py"
)
rl_bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rl_bt)

BORDERS = ("de", "nl", "gb", "no", "se", "dk2")
ISP = timedelta(minutes=15)
LAG = timedelta(minutes=5)  # ISP end + 5 min
LIMIT = 0.98
ICF = ["n_limit_import", "n_limit_export", "net_import_ramp1h", "de_ramp1h"]
RLF = ["rl_last", "rl_ramp1h", "rl_dev_week"]


def first_prints(conn, sid):
    rows = conn.execute(
        "select distinct on (observed_for) observed_for, value from observation"
        " where series_id = %s order by observed_for, published_at, observation_id",
        (sid,),
    ).fetchall()
    return pd.Series({t: float(v) for t, v in rows}).sort_index()


def isp_frame(conn):
    """One row per ISP: flows, net import, residual load, limit flags."""
    df = pd.DataFrame(
        {b: first_prints(conn, f"energinet.dk1.flow_{b}_mw") for b in BORDERS}
    )
    df["rl"] = first_prints(conn, rl_bt.RL)
    df = df.asfreq("15min")
    df["net"] = df[list(BORDERS)].sum(axis=1, min_count=len(BORDERS))
    at_import, at_export = [], []
    for b in BORDERS:
        hi = df[b].clip(lower=0).rolling("28D").max()
        lo = df[b].clip(upper=0).rolling("28D").min()
        at_import.append((df[b] > 0) & (df[b] >= LIMIT * hi))
        at_export.append((df[b] < 0) & (df[b] <= LIMIT * lo))
    df["n_limit_import"] = pd.concat(at_import, axis=1).sum(axis=1)
    df["n_limit_export"] = pd.concat(at_export, axis=1).sum(axis=1)
    df["net_import_ramp1h"] = df.net - df.net.shift(4)
    df["de_ramp1h"] = df.de - df.de.shift(4)
    df["rl_ramp1h"] = df.rl - df.rl.shift(4)
    df["rl_dev_week"] = df.rl - df.rl.shift(freq="7D").reindex(df.index)
    return df.rename(columns={"rl": "rl_last"})


def known_at(frame, targets, horizon):
    """frame's row for the newest ISP visible at each target's freeze."""
    asof = targets.map(lambda t: features.freeze_time(t, horizon))
    last = (asof - ISP - LAG).dt.floor("15min")
    return frame.reindex(last.to_numpy())[ICF + RLF].set_axis(targets.index)


def main():
    with psycopg.connect(DB_URL) as conn:
        frame = isp_frame(conn)
    out = []
    for h in (15, 30, 60):
        every = pd.read_parquet(f"data/training/h{h}.parquet").sort_values("target")
        every = every.join(known_at(frame, every.target, h))
        every = every.dropna(subset=ICF + RLF + replay.LINEAR_LAGS)
        for name in rl_bt.ROUNDS:
            start, end = replay.ROUNDS[name]
            rows = every[(every.target >= start) & (every.target < end)]
            pred = {
                k: rl_bt.fit_predict(rows, every, cols)
                for k, cols in (
                    ("base", []),
                    ("base+ic", ICF),
                    ("rl", RLF),
                    ("rl+ic", RLF + ICF),
                )
            }
            err = {k: p - rows.y for k, p in pred.items()}
            row = {"h": h, "round": name, "n": len(rows)}
            row |= {f"mae_{k}": float(e.abs().mean()) for k, e in err.items()}
            row["share_any_limit"] = float(
                ((rows.n_limit_import + rows.n_limit_export) > 0).mean()
            )
            for a, b in (("base", "base+ic"), ("rl", "rl+ic")):
                g = rl_bt.gain(rows, err[a], err[b])
                row |= {f"{b}_{k}": v for k, v in g.items()}
            out.append(row)
            print(row, flush=True)
    path = HERE / "backtest.csv"
    pd.DataFrame(out).to_csv(path, index=False, float_format="%.3f")
    print(f"wrote {path}")
    # how often each border sits at its limit, 1 Oct 2025 - 28 Oct 2026
    w = frame.loc["2025-10-01":"2026-10-28"]
    for b in BORDERS:
        hi = w[b].clip(lower=0).rolling("28D").max()
        lo = w[b].clip(upper=0).rolling("28D").min()
        imp = ((w[b] > 0) & (w[b] >= LIMIT * hi)).mean()
        exp = ((w[b] < 0) & (w[b] <= LIMIT * lo)).mean()
        print(f"{b}: at import limit {imp:.1%}, at export limit {exp:.1%},"
              f" mean {w[b].mean():.0f} MW, range {w[b].min():.0f} to {w[b].max():.0f}")  # fmt: skip


if __name__ == "__main__":
    main()
