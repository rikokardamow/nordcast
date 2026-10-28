"""LightGBM calls for DK1: volume quantiles and a calibrated direction.

One model set per horizon (15, 30, 60 min). Trained on the clean window
from 1 Oct 2025 (15-min day-ahead on every layer), with the 4 Mar 2026
break as a feature (`regime_activated`), never pooled blind.

Splits, in time order over the window:
  fit        first 60 %   the boosters
  calibrate  60-80 %      isotonic for direction, conformal (MAPIE) for volume
  validate   last 20 %    hyperparameters are chosen here, and the 03
                          notebook reports here, so its scorecard is
                          optimistic by that choice; the replay (step 5)
                          and the live record are the honest tests.
The final models fit on the first 80 % and calibrate on the last 20 %.
"""

import hashlib
import pickle
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from nordcast import baselines, features
from nordcast.baselines import MissingData

WINDOW_START = datetime(2025, 10, 1, tzinfo=UTC)
CLASSES = ("down", "none", "up")
QUANTILES = (0.1, 0.5, 0.9)
GRID = [
    {
        "num_leaves": nl,
        "n_estimators": n,
        "learning_rate": 0.05,
        "min_child_samples": 50,
    }
    for nl in (7, 15, 31)
    for n in (150, 300, 600)
]
ISP = timedelta(minutes=15)


def build_rows(pit, targets, horizon):
    """Feature rows with first-print labels and the persistence call beside them."""
    rows = []
    for t in targets:
        asof = features.freeze_time(t, horizon)
        volume, direction = features.label(pit, t)
        if volume is None or direction is None:
            continue
        try:
            f = features.features(pit.history, t, horizon, asof)
            p = baselines.persistence(pit.history, t, asof)
            pd_ = baselines.direction_persistence(pit.history, t, asof)
        except MissingData:
            continue
        imb, _ = pit.first(features.S + "imbalance_price_eur", t)
        da = pit.value(features.S + "da_price_eur", t, asof)
        rows.append(
            {
                "target": t,
                **f,
                "y": volume,
                "y_dir": direction,
                "pers_point": p["point"],
                "pers_q10": p["q10"],
                "pers_q90": p["q90"],
                "pers_dir": pd_["direction"],
                "imb_price": imb,
                "da_price_target": da,
            }
        )
    return pd.DataFrame(rows)


FEATURES_DROP = {
    "target", "y", "y_dir", "pers_point", "pers_q10", "pers_q90", "pers_dir",
    "imb_price", "da_price_target",
}  # fmt: skip


def X(df):
    return df[[c for c in df.columns if c not in FEATURES_DROP]].astype(float)


def split(df):
    df = df.sort_values("target").reset_index(drop=True)
    a, b = int(len(df) * 0.6), int(len(df) * 0.8)
    return df.iloc[:a], df.iloc[a:b], df.iloc[b:]


def pinball(y, q, tau):
    d = np.asarray(y) - np.asarray(q)
    return float(np.mean(np.maximum(tau * d, (tau - 1) * d)))


def brier(probs, y_dir):
    onehot = np.array([[c == d for c in CLASSES] for d in y_dir], dtype=float)
    return float(np.mean(np.sum((probs - onehot) ** 2, axis=1)))


@dataclass
class Fitted:
    horizon: int
    params: dict  # {"volume": {...}, "direction": {...}}
    quantile: dict = field(default_factory=dict)  # tau -> LGBMRegressor
    conformal: object = None  # MAPIE ConformalizedQuantileRegressor, 80 %
    direction: object = None  # calibrated classifier
    feature_names: list = field(default_factory=list)

    def predict(self, frame):
        x = X(frame)[self.feature_names]
        q = {tau: m.predict(x) for tau, m in self.quantile.items()}
        _, pis = self.conformal.predict_interval(x)
        probs = self.direction.predict_proba(x)
        order = [list(self.direction.classes_).index(c) for c in CLASSES]
        return pd.DataFrame(
            {
                "q10": np.minimum(pis[:, 0, 0], q[0.5]),
                "q50": q[0.5],
                "q90": np.maximum(pis[:, 1, 0], q[0.5]),
                "q10_raw": q[0.1],
                "q90_raw": q[0.9],
                "p_down": probs[:, order[0]],
                "p_none": probs[:, order[1]],
                "p_up": probs[:, order[2]],
            },
            index=frame.index,
        )

    def digest(self):
        return hashlib.sha256(pickle.dumps(self)).hexdigest()


def _fit(horizon, params, fit, calibrate):
    """params: {"volume": lightgbm settings, "direction": lightgbm settings}."""
    import lightgbm as lgb
    from mapie.regression import ConformalizedQuantileRegressor
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.frozen import FrozenEstimator

    fixed = {"verbose": -1, "random_state": 7}
    vol, dirn = {**params["volume"], **fixed}, {**params["direction"], **fixed}
    m = Fitted(horizon, params, feature_names=list(X(fit).columns))
    for tau in QUANTILES:
        m.quantile[tau] = lgb.LGBMRegressor(objective="quantile", alpha=tau, **vol).fit(
            X(fit), fit.y
        )
    m.conformal = ConformalizedQuantileRegressor(
        lgb.LGBMRegressor(objective="quantile", alpha=0.5, **vol),
        confidence_level=0.8,
    )
    m.conformal.fit(X(fit), fit.y).conformalize(X(calibrate), calibrate.y)
    clf = lgb.LGBMClassifier(objective="multiclass", **dirn).fit(X(fit), fit.y_dir)
    m.direction = CalibratedClassifierCV(FrozenEstimator(clf), method="isotonic")
    m.direction.fit(X(calibrate), calibrate.y_dir)
    return m


def score_frame(df, pred):
    """The scorecard row for one prediction frame against first prints."""
    probs = pred[["p_down", "p_none", "p_up"]].to_numpy()
    called = np.array(CLASSES)[probs.argmax(axis=1)]
    return {
        "n": len(df),
        "mae": float(np.mean(np.abs(df.y - pred.q50))),
        "pinball": np.mean(
            [pinball(df.y, pred[f"q{int(t * 100)}"], t) for t in QUANTILES]
        ),
        "coverage": float(np.mean((df.y >= pred.q10) & (df.y <= pred.q90))),
        "direction_acc": float(np.mean(called == df.y_dir)),
        "brier": brier(probs, df.y_dir),
        "pnl_eur": pnl(df, called),
    }


def persistence_frame(df):
    onehot = {c: (df.pers_dir == c).astype(float) for c in CLASSES}
    return pd.DataFrame(
        {"q10": df.pers_q10, "q50": df.pers_point, "q90": df.pers_q90,
         "p_down": onehot["down"], "p_none": onehot["none"], "p_up": onehot["up"]},
        index=df.index,
    )  # fmt: skip


def pnl(df, called, mw=10):
    """Hold-into-imbalance: leave `mw` open in the called direction for the
    ISP, settled at the first-print imbalance price against day-ahead.
    Long when up is called (the system is short, imbalance above day-ahead),
    short when down, flat on none. EUR, summed."""
    sign = np.select([called == "up", called == "down"], [1.0, -1.0], 0.0)
    spread = (df.imb_price - df.da_price_target).to_numpy(dtype=float)
    ok = ~np.isnan(spread)
    return float(np.sum(sign[ok] * mw * 0.25 * spread[ok]))


def split_since(df, since=None):
    """split(), with fit and calibrate cut to targets from `since` (75/25 of
    what's left before the validation slice). Validation is unchanged, so a
    shorter window is scored on exactly the same ISPs."""
    fit, calibrate, validate = split(df)
    if since is None:
        return fit, calibrate, validate
    before = pd.concat([fit, calibrate])
    before = before[before.target >= since]
    a = int(len(before) * 0.75)
    return before.iloc[:a], before.iloc[a:], validate


def select_and_fit(df, horizon, grid=GRID, since=None):
    """Choose volume settings by pinball and direction settings by Brier, each
    on the last 20 %. Returns (model fitted on the first 60 % for the
    validation scorecard, final model on the whole window, the grid's results)."""
    fit, calibrate, validate = split_since(df, since)
    results = []
    for params in grid:
        m = _fit(horizon, {"volume": params, "direction": params}, fit, calibrate)
        results.append({**params, **score_frame(validate, m.predict(validate))})
    keys = list(GRID[0])
    chosen = {
        "volume": {k: min(results, key=lambda r: r["pinball"])[k] for k in keys},
        "direction": {k: min(results, key=lambda r: r["brier"])[k] for k in keys},
    }
    holdout = _fit(horizon, chosen, fit, calibrate)
    # the whole window: boosters on the first 80 %, calibration on the last 20 %
    final = _fit(horizon, chosen, pd.concat([fit, calibrate]), validate)
    return holdout, final, pd.DataFrame(results)
