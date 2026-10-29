"""The calls the layers read, until the live record has enough of its own.

    uv run --all-groups python jobs/layer_calls.py

Writes data/layers/calls_h<h>.parquet: every ISP from 1 Oct 2025 to the end of
the training rows, flagged `replay_window` up to the end of the replay's last
round (L1 and L2 report on that window; L3's stress reaches past it to the
20-26 Oct 2026 storm week), the replay's winner, ar(1), as
`point/q10/q90`, persistence as `pers_*`, and the first prints. Built from the
step-4 training rows and the replay's own point-in-time history, so each call
uses only what was public at its freeze. Estimated vintages: not the record.
"""

from datetime import timedelta
from pathlib import Path

import pandas as pd
import psycopg
from _common import DB_URL

from nordcast import features, freeze, replay
from nordcast.baselines import TARGET

OUT = Path("data/layers")
KEEP = ["target", "steps_ahead", "hour", "quarter", "weekday", "regime_activated",
        "wind_onshore_err_da_last", "wind_offshore_err_da_last", "pers_point",
        "pers_q10", "pers_q90", "pers_dir", "y", "y_dir", "imb_price",
        "da_price_target"]  # fmt: skip

start = min(s for s, _ in replay.ROUNDS.values())
replay_end = max(e for _, e in replay.ROUNDS.values())
end = pd.read_parquet(Path("data/training") / "h15.parquet").target.max() + timedelta(
    minutes=15
)
with psycopg.connect(DB_URL) as conn:
    pit = features.load(conn, start - timedelta(days=35), end, [TARGET])
OUT.mkdir(parents=True, exist_ok=True)
for h in freeze.HORIZONS:
    rows = pd.read_parquet(Path("data/training") / f"h{h}.parquet")
    rows = rows[(rows.target >= start) & (rows.target < end)].sort_values("target")
    ar1 = replay.persistence_ar1(rows, None, {"pit": pit, "horizon": h})
    calls = rows[KEEP].join(ar1[["q10", "q50", "q90"]].rename(columns={"q50": "point"}))
    calls["replay_window"] = calls.target < replay_end
    calls.to_parquet(OUT / f"calls_h{h}.parquet")
    print(
        f"h{h}: {len(calls)} calls, {calls.target.min():%d %b %Y} .. {calls.target.max():%d %b %Y}"
    )
