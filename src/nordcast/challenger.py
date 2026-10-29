"""LightGBM v1 frozen live beside persistence: a challenger, never the headline.

It earns the headline only through notes/preregistration.md, at a quarter
boundary (1 Apr 2027 at the earliest).

Training saw backfilled vintages, published at a nominal lag that errs late
(each Series.lag in sources/energinet.py); live, the archive's first prints come
sooner, so the target's latest known ISP is one fresher than any row the
model was fitted on. `nominal()` hides what training couldn't have seen, and
the features are read at the training freeze time (T - h - 5 min) or now,
whichever is earlier. The model sees live what it saw in training, never
more.

Models are the final fits from jobs/train.py in data/models/, checked
against the manifest's sha256 before the first call.
"""

import hashlib
import json
import pickle
from pathlib import Path

from nordcast import features
from nordcast.sources import energinet

TAG = "lightgbm-v1"
METHOD = "lightgbm_v1"
MODELS = Path(__file__).parents[2] / "data" / "models"


class ModelMismatch(Exception):
    pass


def nominal(history):
    """history_asof that only returns a period once its nominal lag has passed,
    as floats: the database returns Decimal, training's PointInTime float."""

    def view(sid, from_ts, to_ts, asof):
        values = {p: float(v) for p, v in history(sid, from_ts, to_ts, asof).items()}
        spec = energinet.SERIES.get(sid)
        if spec is None:
            return values
        return {p: v for p, v in values.items() if spec.lag(p) <= asof}

    return view


def load(models=MODELS, tag=TAG):
    """{horizon: (Fitted, sha256)}, each pickle checked against the manifest."""
    manifest = json.loads((Path(models) / f"manifest-{tag}.json").read_text())
    out = {}
    for key, entry in manifest["models"].items():
        blob = (Path(models) / f"{tag}-{key}.pkl").read_bytes()
        digest = hashlib.sha256(blob).hexdigest()
        if digest != entry["sha256"]:
            raise ModelMismatch(f"{tag}-{key}.pkl is {digest[:12]}, manifest says"
                                f" {entry['sha256'][:12]}")  # fmt: skip
        out[int(key.removeprefix("h"))] = (pickle.loads(blob), digest)
    return out


def lightgbm(fitted):
    """A challenger: (history, target, now, horizon) -> call."""
    import pandas as pd

    from nordcast.model import CLASSES

    def call(history, target, now, horizon):
        m, digest = fitted[horizon]
        asof = min(now, features.freeze_time(target, horizon))
        f = features.features(nominal(history), target, horizon, asof)
        p = m.predict(pd.DataFrame([f])).iloc[0]
        probs = {c: float(p[f"p_{c}"]) for c in CLASSES}
        return {
            "point": float(p.q50),
            "q10": float(p.q10),
            "q50": float(p.q50),
            "q90": float(p.q90),
            "direction": max(probs, key=probs.get),
            **{f"p_{c}": v for c, v in probs.items()},
            "model_version": f"{TAG}@{digest[:12]}",
        }

    return call
