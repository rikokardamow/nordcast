"""The replay: walk-forward rounds over the clean window, per notes/replay.md.

A round is a Copenhagen quarter. Forecasts come from the step-4 training
rows (data/training/h<h>.parquet): each row holds the features as of the
ISP's freeze time, the first-print labels and the persistence call, all
built through the same point-in-time history as the live freeze. A method
fitted for a round sees only rows whose ISP is before the round starts.

Nothing here is the record: estimated vintages, never frozen or stamped.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from nordcast import model

CPH = ZoneInfo("Europe/Copenhagen")
ROUNDS = {
    "2025q4": (datetime(2025, 10, 1, tzinfo=CPH), datetime(2026, 1, 1, tzinfo=CPH)),
    "2026q1": (datetime(2026, 1, 1, tzinfo=CPH), datetime(2026, 4, 1, tzinfo=CPH)),
    "2026q2": (datetime(2026, 4, 1, tzinfo=CPH), datetime(2026, 7, 1, tzinfo=CPH)),
    "2026q3": (datetime(2026, 7, 1, tzinfo=CPH), datetime(2026, 10, 1, tzinfo=CPH)),
}
WIND_BUCKETS = [-np.inf, -300, -100, 100, 300, np.inf]


def round_rows(df, name):
    start, end = ROUNDS[name]
    return df[(df.target >= start) & (df.target < end)].sort_values("target")


def training_rows(df, name):
    start, _ = ROUNDS[name]
    return df[df.target < start].sort_values("target")


def persistence(rows, train=None):
    return model.persistence_frame(rows)


METHODS = {"persistence": persistence}


def scorecard(rows, pred):
    """The round's scorecard line for one method and horizon."""
    s = model.score_frame(rows, pred)
    err = pred.q50 - rows.y
    nonzero = rows.y != 0
    s["rmse"] = float(np.sqrt(np.mean(err**2)))
    s["sign"] = float(np.mean(np.sign(pred.q50[nonzero]) == np.sign(rows.y[nonzero])))
    return s


def diagnostics(rows, pred):
    """Error by hour, by onshore wind error bucket, residual acf, top misses."""
    err = (pred.q50 - rows.y).rename("error")
    d = rows.assign(error=err, abs_error=err.abs(), pred=pred.q50)
    by_hour = d.groupby("hour").abs_error.mean()
    buckets = pd.cut(d.wind_onshore_err_da_last, WIND_BUCKETS)
    by_wind = d.groupby(buckets, observed=False).agg(
        n=("abs_error", "size"), mae=("abs_error", "mean")
    )
    e = err.to_numpy() - err.mean()
    acf = {k: float(np.dot(e[:-k], e[k:]) / np.dot(e, e)) for k in (1, 2, 4, 8, 96)}
    cols = ["target", "y", "pred", "error", "sd_lag1", "steps_ahead",
            "wind_onshore_err_da_last", "wind_offshore_err_da_last", "hour"]  # fmt: skip
    worst = d.reindex(d.abs_error.sort_values(ascending=False).index).head(10)[cols]
    return {"by_hour": by_hour, "by_wind": by_wind, "acf": acf, "worst": worst}
