"""Builds 04_weather.ipynb: does HARMONIE point wind add to lightgbm-v1's inputs?

uv run --all-groups python notebooks/build_04_weather.py
uv run --all-groups jupyter nbconvert --execute --inplace notebooks/04_weather.ipynb
"""

from pathlib import Path

import nbformat as nbf

md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell

cells = [
    md(
        "# 04 – does the weather add anything?\n\n"
        "Every replay round's worst misses were wind surprises the target's own history can't "
        "see (notes/replay-log.md). This tests the most direct fix: DMI HARMONIE 100 m wind at the "
        "six DK1 points, as forecast a day earlier (sources/open_meteo.py), added to lightgbm-v1's "
        "own feature rows. Same rows, same split (fit 60 % / calibrate 20 % / validate 20 %), same "
        "settings as v1; only the weather columns differ. Volume quantiles (q10/q50/q90) only, "
        "pinball on the last 20 %, with a 90 % interval from resampling Copenhagen days. Estimated "
        "vintages: a research result, not the record, and not a change to the pre-registered v1."
    ),
    code(
        """import json
from datetime import timedelta
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import psycopg

from nordcast import features, model
from nordcast.sources import open_meteo

URL = "postgresql://postgres:postgres@127.0.0.1:44332/postgres"
ONSHORE, OFFSHORE = ["romo", "hvide_sande", "hanstholm", "skagen"], ["horns_rev", "anholt"]
SIDS = [open_meteo.series_id(p, "ws100") for p in ONSHORE + OFFSHORE]
v1 = json.loads(Path("../data/models/manifest-lightgbm-v1.json").read_text())
with psycopg.connect(URL) as conn:
    pit = features.load(conn, pd.Timestamp("2025-09-01", tz="UTC"), pd.Timestamp("2026-11-01", tz="UTC"), SIDS)


def mean_wind(points, at, asof):
    v = [pit.value(open_meteo.series_id(p, "ws100"), at, asof) for p in points]
    v = [x for x in v if x is not None]
    return sum(v) / len(v) if v else np.nan


def weather(rows, h):
    \"\"\"Point-in-time wind at the target hour and the hour before, as of the freeze.\"\"\"
    out = []
    for t in rows.target:
        t = t.to_pydatetime()
        asof = features.freeze_time(t, h)
        hour, before = t.replace(minute=0), t.replace(minute=0) - timedelta(hours=1)
        on, off = mean_wind(ONSHORE, hour, asof), mean_wind(OFFSHORE, hour, asof)
        out.append({"ws_on": on, "ws_off": off,
                    "ws_on_ramp": on - mean_wind(ONSHORE, before, asof),
                    "ws_off_ramp": off - mean_wind(OFFSHORE, before, asof)})
    return pd.DataFrame(out, index=rows.index)


def pinball_by_isp(y, preds):
    return np.mean([np.maximum(t * (y - preds[t]), (t - 1) * (y - preds[t])) for t in model.QUANTILES], axis=0)


rows, daily_d = [], {}
for h in (15, 30, 60):
    df = pd.read_parquet(f"../data/training/h{h}.parquet").sort_values("target").reset_index(drop=True)
    df = df.join(weather(df, h))
    fit, cal, val = model.split(df)
    params = {**v1["models"][f"h{h}"]["params"]["volume"], "verbose": -1, "random_state": 7}
    base_cols = list(model.X(df.drop(columns=["ws_on", "ws_off", "ws_on_ramp", "ws_off_ramp"])).columns)
    loss = {}
    for name, cols in (("v1 inputs", base_cols), ("v1 + weather", base_cols + ["ws_on", "ws_off", "ws_on_ramp", "ws_off_ramp"])):
        x_fit, x_val = fit[cols].astype(float), val[cols].astype(float)
        preds = {t: lgb.LGBMRegressor(objective="quantile", alpha=t, **params).fit(x_fit, fit.y).predict(x_val)
                 for t in model.QUANTILES}
        loss[name] = pinball_by_isp(val.y.to_numpy(), preds)
        rows.append({"h": h, "inputs": name, "pinball": loss[name].mean(),
                     "mae_q50": np.abs(val.y - preds[0.5]).mean(),
                     "weather_missing": float(val[["ws_on"]].isna().mean().iloc[0])})
    d = pd.Series(loss["v1 inputs"] - loss["v1 + weather"], index=val.target)
    daily_d[h] = d.groupby(d.index.tz_convert("Europe/Copenhagen").date).mean()
card = pd.DataFrame(rows).set_index(["h", "inputs"])
card.round(3)"""
    ),
    md(
        "**The number:** the mean daily pinball improvement from adding the weather (positive = the "
        "weather helps), with a 90 % interval from resampling Copenhagen days."
    ),
    code(
        """rng = np.random.default_rng(20261029)
out = {}
for h, d in daily_d.items():
    a = d.to_numpy()
    means = a[rng.integers(0, len(a), (10_000, len(a)))].mean(1)
    out[h] = {"mean_daily_improvement": a.mean(), "lo_90": np.quantile(means, 0.05),
              "hi_90": np.quantile(means, 0.95), "days": len(a),
              "relative": a.mean() / card.loc[(h, "v1 inputs"), "pinball"]}
pd.DataFrame(out).T.round(4)"""
    ),
    md(
        "## How to read it\n\n"
        "An interval that sits above zero means the weather adds information v1's inputs don't "
        "carry: a case for a lightgbm-v2 challenger, frozen beside v1 from a quarter boundary and "
        "pre-registered like it. An interval across zero means v1's own wind inputs (Energinet's "
        "forecasts and their recent errors) already carry what HARMONIE's point wind adds, at these "
        "horizons."
    ),
    md(
        "## Result, 29 Oct 2026\n\n"
        "Next to nothing. At 15 min the weather lowers pinball by 0.4 % (interval just above zero), "
        "at 30 min it raises it by 0.4 % (interval below zero), at 60 min it's level. Energinet's "
        "own wind forecasts and their recent errors, already in v1, carry what the point wind adds. "
        "No case for a weather-based v2. The archive keeps collecting HARMONIE versions anyway: a "
        "shorter-horizon model or intraday runs may use them, and the history can't be bought later."
    ),
]

nb = nbf.v4.new_notebook(cells=cells)
nb.metadata["kernelspec"] = {
    "name": "python3",
    "display_name": "Python 3",
    "language": "python",
}
Path(__file__).with_name("04_weather.ipynb").write_text(nbf.writes(nb))
