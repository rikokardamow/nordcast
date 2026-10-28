"""The replay: walk-forward rounds over the clean window, per notes/replay.md.

A round is a Copenhagen quarter. Forecasts come from the step-4 training
rows (data/training/h<h>.parquet): each row holds the features as of the
ISP's freeze time, the first-print labels and the persistence call, all
built through the same point-in-time history as the live freeze. A method
fitted for a round sees only rows whose ISP is before the round starts.

Nothing here is the record: estimated vintages, never frozen or stamped.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from nordcast import baselines, features, model

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


def persistence(rows, train, ctx):
    return model.persistence_frame(rows)


def persistence_ar1(rows, train, ctx):
    """The live baseline itself: phi and the mean refit on the 7 days before
    each freeze. Volume only; its direction is persistence's, so direction
    rows score the same as persistence."""
    out = []
    for t in rows.target:
        asof = features.freeze_time(t.to_pydatetime(), ctx["horizon"])
        c = baselines.persistence_ar1(ctx["pit"].history, t.to_pydatetime(), asof)
        out.append((c["q10"], c["point"], c["q90"]))
    q = pd.DataFrame(out, columns=["q10", "q50", "q90"], index=rows.index)
    return q.join(model.persistence_frame(rows)[["p_down", "p_none", "p_up"]])


def _seasonal(lag):
    """Same ISP `lag` earlier, as first known by the freeze; the band is the
    10th/90th percentile of `lag` changes over the 7 days before the freeze."""

    def method(rows, train, ctx):
        out = []
        for t in rows.target:
            t = t.to_pydatetime()
            asof = features.freeze_time(t, ctx["horizon"])
            vals = ctx["pit"].history(
                baselines.TARGET, asof - timedelta(days=7) - lag, asof, asof
            )
            point = vals.get(t - lag)
            changes = [v - vals[p - lag] for p, v in vals.items() if p - lag in vals]
            if point is None or len(changes) < 96:
                out.append((np.nan, np.nan, np.nan))  # counted as missing, never filled
                continue
            out.append(
                (
                    point + np.quantile(changes, 0.1),
                    point,
                    point + np.quantile(changes, 0.9),
                )
            )
        q = pd.DataFrame(out, columns=["q10", "q50", "q90"], index=rows.index)
        return q.join(model.persistence_frame(rows)[["p_down", "p_none", "p_up"]])

    return method


LINEAR_LAGS = [
    "sd_lag1",
    "sd_lag2",
    "sd_lag3",
    "sd_lag4",
    "sd_mean4",
    "regime_activated",
]
LABEL_DELAY = timedelta(days=1)  # a label is used for fitting only a day after its ISP


def _design(rows):
    x = rows[LINEAR_LAGS].astype(float)
    for col, n in (("hour", 24), ("quarter", 4), ("weekday", 7)):
        for k in range(1, n):  # one level dropped against the intercept
            x[f"{col}_{k}"] = (rows[col] == k).astype(float)
    x.insert(0, "const", 1.0)
    return x


def linear_lags_calendar(rows, train, ctx):
    """Rung 4: least squares on the target's lags and calendar dummies,
    refit each Monday (Copenhagen) on every row whose ISP was a day old by
    then. Band: 10th / 90th percentile of the fit's own residuals."""
    every = ctx["all"]
    out = pd.DataFrame(np.nan, index=rows.index, columns=["q10", "q50", "q90"])
    local = rows.target.dt.tz_convert(CPH)
    weeks = (local - pd.to_timedelta(local.dt.day_of_week, unit="D")).dt.normalize()
    for week, idx in rows.groupby(weeks).groups.items():
        fit = every[every.target < week - LABEL_DELAY]
        fx = _design(fit)
        ok = fx.notna().all(axis=1)
        beta, *_ = np.linalg.lstsq(fx[ok].to_numpy(), fit.y[ok].to_numpy(), rcond=None)
        resid = fit.y[ok].to_numpy() - fx[ok].to_numpy() @ beta
        lo, hi = np.quantile(resid, [0.1, 0.9])
        x = _design(rows.loc[idx])
        good = x.notna().all(axis=1)
        point = x[good].to_numpy() @ beta
        out.loc[x.index[good], ["q10", "q50", "q90"]] = np.c_[
            point + lo, point, point + hi
        ]
    return out.join(model.persistence_frame(rows)[["p_down", "p_none", "p_up"]])


METHODS = {
    "linear_lags_calendar": linear_lags_calendar,
    "persistence": persistence,
    "persistence_ar1": persistence_ar1,
    "seasonal_naive_day": _seasonal(timedelta(days=1)),
    "seasonal_naive_week": _seasonal(timedelta(days=7)),
}


def scorecard(rows, pred):
    """The round's scorecard line for one method and horizon. ISPs a method
    couldn't forecast are counted in `missing` and left out, never filled."""
    ok = pred.q50.notna()
    missing = int((~ok).sum())
    rows, pred = rows[ok], pred[ok]
    s = model.score_frame(rows, pred)
    s["missing"] = missing
    err = pred.q50 - rows.y
    nonzero = rows.y != 0
    s["rmse"] = float(np.sqrt(np.mean(err**2)))
    s["sign"] = float(np.mean(np.sign(pred.q50[nonzero]) == np.sign(rows.y[nonzero])))
    return s


def diagnostics(rows, pred):
    """Error by hour, by onshore wind error bucket, residual acf, top misses."""
    ok = pred.q50.notna()
    rows, pred = rows[ok], pred[ok]
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
    regime = d.groupby("regime_activated").abs_error.agg(["mean", "size"])
    by_regime = {
        ("after" if k else "before"): (float(r["mean"]), int(r["size"]))
        for k, r in regime.iterrows()
    }
    return {"by_hour": by_hour, "by_wind": by_wind, "acf": acf, "worst": worst,
            "by_regime": by_regime}  # fmt: skip
