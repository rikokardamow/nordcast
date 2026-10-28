"""Train and save the LightGBM model set for every horizon.

    uv run --all-groups python jobs/train.py

Reads data/training/h<h>.parquet (jobs/build_training.py). Writes
data/models/lightgbm-v1-h<h>.pkl (the final model) and
data/models/holdout-h<h>.pkl (fitted on the first 60 %, for the scorecard),
plus data/models/grid-h<h>.csv and a manifest with each artefact's sha256.
"""

import argparse
import json
import pickle
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from nordcast import freeze, model

ap = argparse.ArgumentParser()
ap.add_argument("--since", type=lambda d: datetime.fromisoformat(d).replace(tzinfo=UTC))
ap.add_argument("--tag", default="lightgbm-v1")
args = ap.parse_args()
DATA, OUT = Path("data/training"), Path("data/models")
OUT.mkdir(parents=True, exist_ok=True)
commit = subprocess.run(
    ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
).stdout.strip()
manifest = {"code_commit": commit, "tag": args.tag, "models": {}}
for h in freeze.HORIZONS:
    df = pd.read_parquet(DATA / f"h{h}.parquet")
    holdout, final, grid = model.select_and_fit(df, h, since=args.since)
    grid.to_csv(OUT / f"grid-{args.tag}-h{h}.csv", index=False)
    for name, m in ((f"holdout-{args.tag}", holdout), (args.tag, final)):
        (OUT / f"{name}-h{h}.pkl").write_bytes(pickle.dumps(m))
    manifest["models"][f"h{h}"] = {
        "params": final.params,
        "sha256": final.digest(),
        "rows": len(df),
        "window": [str(df.target.min()), str(df.target.max())],
    }
    print(f"h{h}: {final.params}")
manifest["since"] = str(args.since)
(OUT / f"manifest-{args.tag}.json").write_text(json.dumps(manifest, indent=2) + "\n")
