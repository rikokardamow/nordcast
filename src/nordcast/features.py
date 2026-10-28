"""Features for one DK1 call: everything public at the freeze, nothing later.

Every value is read through `history(series_id, from_ts, to_ts, asof)`, the
same contract as store.history_asof, so a feature can only see vintages
published by `asof`. Live, `history` is the database; for training and the
replay it's PointInTime, the same lookup over the observation table in memory
(tested equal to the database function).

A training row for target ISP T and horizon h uses asof = T - h - 5 min: the
live freeze runs in the 5 minutes before T - h, so this is the earliest it
can, and the least it can know.

Missing inputs are None. LightGBM routes them down a learned branch; that's
written in the model card. The one input without which there is no call,
the latest target value, raises MissingData instead.
"""

import bisect
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from nordcast.baselines import CODE, DIRECTION, TARGET, MissingData

COPENHAGEN = ZoneInfo("Europe/Copenhagen")
ISP = timedelta(minutes=15)
FREEZE_SLACK = timedelta(minutes=5)
REGIME_BREAK = datetime(
    2026, 3, 4, tzinfo=ZoneInfo("UTC")
)  # SatisfiedDemand: demand -> activated

S = "energinet.dk1."
SERIES = [
    TARGET,
    DIRECTION,
    S + "imbalance_price_eur",
    S + "afrr_up_mw",
    S + "afrr_down_mw",
    S + "mfrr_up_mw",
    S + "mfrr_down_mw",
    S + "da_price_eur",
    S + "wind_onshore_mw",
    S + "wind_offshore_mw",
    S + "solar_mw",
    S + "wind_onshore_fc_da_mw",
    S + "wind_offshore_fc_da_mw",
    S + "solar_fc_da_mw",
    S + "wind_onshore_fc_1h_mw",
    S + "wind_offshore_fc_1h_mw",
]


def freeze_time(target, horizon):
    return target - timedelta(minutes=horizon) - FREEZE_SLACK


class PointInTime:
    """store.history_asof over rows held in memory.

    rows: (series_id, observed_for, value, published_at) in observation_id
    order, so of two vintages published at the same instant the later wins,
    as in the database."""

    def __init__(self, rows):
        by = defaultdict(lambda: defaultdict(list))
        for sid, period, value, published in rows:
            by[sid][period].append((published, float(value)))
        self._v = {}
        for sid, periods in by.items():
            self._v[sid] = {}
            for period, vs in periods.items():
                vs.sort(key=lambda pv: pv[0])  # stable: equal times keep id order
                self._v[sid][period] = ([p for p, _ in vs], [v for _, v in vs])
        self._periods = {sid: sorted(ps) for sid, ps in self._v.items()}

    def value(self, sid, period, asof):
        times, values = self._v.get(sid, {}).get(period, ((), ()))
        i = bisect.bisect_right(times, asof)
        return values[i - 1] if i else None

    def first(self, sid, period):
        """The first print, the value every call is scored against."""
        times, values = self._v.get(sid, {}).get(period, ((), ()))
        return (values[0], times[0]) if times else (None, None)

    def history(self, sid, from_ts, to_ts, asof):
        periods = self._periods.get(sid, [])
        lo, hi = (
            bisect.bisect_left(periods, from_ts),
            bisect.bisect_left(periods, to_ts),
        )
        out = {}
        for p in periods[lo:hi]:
            v = self.value(sid, p, asof)
            if v is not None:
                out[p] = v
        return out


def load(conn, start, end, series=SERIES):
    """A PointInTime for every vintage of `series` observed in [start, end)."""
    rows = conn.execute(
        "select series_id, observed_for, value, published_at from observation"
        " where series_id = any(%s) and observed_for >= %s and observed_for < %s"
        " order by observation_id",
        (list(series), start, end),
    ).fetchall()
    return PointInTime(rows)


def _latest(history, sid, asof, span):
    """(isp, value) of the newest ISP known at asof within `span`, or (None, None)."""
    vs = history(sid, asof - span, asof, asof)
    if not vs:
        return None, None
    isp = max(vs)
    return isp, vs[isp]


def _at(history, sid, period, asof):
    return history(sid, period, period + ISP, asof).get(period)


def _sub(a, b):
    return None if a is None or b is None else a - b


def features(history, target, horizon, asof):
    """{name: value or None} for one call."""
    recent = history(TARGET, asof - timedelta(hours=3), asof, asof)
    if not recent:
        raise MissingData(f"no {TARGET} known in the 3 h before {asof}")
    last_isp = max(recent)
    if asof - last_isp > timedelta(hours=2):
        raise MissingData(f"latest {TARGET} ({last_isp}) is stale at {asof}")
    lags = [recent.get(last_isp - k * ISP) for k in range(8)]
    known = [v for v in lags if v is not None]
    local = target.astimezone(COPENHAGEN)

    f = {
        "horizon_min": horizon,
        "hour": local.hour,
        "quarter": local.minute // 15,
        "weekday": local.weekday(),
        "regime_activated": int(target >= REGIME_BREAK),
        "steps_ahead": round((target - last_isp) / ISP),
        "sd_lag1": lags[0],
        "sd_lag2": lags[1],
        "sd_lag3": lags[2],
        "sd_lag4": lags[3],
        "sd_mean4": sum(known[:4]) / len(known[:4]),
        "sd_std8": (
            (sum((v - sum(known) / len(known)) ** 2 for v in known) / len(known)) ** 0.5
            if len(known) > 1
            else None
        ),
    }
    _, d = _latest(history, DIRECTION, asof, timedelta(hours=2))
    f["dir_last"] = None if d is None else int(d)
    for name in ("afrr_up_mw", "afrr_down_mw", "mfrr_up_mw", "mfrr_down_mw"):
        _, f[name + "_last"] = _latest(history, S + name, asof, timedelta(hours=3))

    da_target = _at(history, S + "da_price_eur", target, asof)
    imb_isp, imb = _latest(history, S + "imbalance_price_eur", asof, timedelta(hours=3))
    f["da_price"] = da_target
    f["imb_minus_da_last"] = (
        None
        if imb_isp is None
        else _sub(imb, _at(history, S + "da_price_eur", imb_isp, asof))
    )
    f["da_price_step"] = _sub(
        da_target, _at(history, S + "da_price_eur", target - ISP, asof)
    )

    for kind in ("wind_onshore", "wind_offshore", "solar"):
        actual = history(S + f"{kind}_mw", asof - timedelta(hours=1), asof, asof)
        fc_da = S + f"{kind}_fc_da_mw"
        f[f"{kind}_fc_da"] = _at(history, fc_da, target, asof)
        errors = [
            _sub(v, _at(history, fc_da, t, asof))
            for t, v in sorted(actual.items())[-4:]
        ]
        errors = [e for e in errors if e is not None]
        f[f"{kind}_err_da_last"] = errors[-1] if errors else None
        f[f"{kind}_err_da_mean4"] = sum(errors) / len(errors) if errors else None
        if kind != "solar":
            fc_1h = _at(history, S + f"{kind}_fc_1h_mw", target, asof)
            f[f"{kind}_fc_1h"] = fc_1h
            f[f"{kind}_fc_1h_minus_da"] = _sub(fc_1h, f[f"{kind}_fc_da"])
    return f


def label(pit, target):
    """(volume, direction) as first printed, or (None, None)."""
    v, _ = pit.first(TARGET, target)
    d, _ = pit.first(DIRECTION, target)
    return v, (None if d is None else CODE[int(d)])
