"""The baselines every DK1 call is scored against.

All read through `history(series_id, from_ts, to_ts, asof) -> {isp: value}`,
normally store.history_asof bound to a connection, so they see exactly what
was public at `asof` and run in a backtest without a database.

The latest ISP known at a freeze is a few ISPs before the target: the first
print comes ~10 min after an ISP ends, and the call is frozen h minutes
before the target starts. `steps` is that gap in ISPs.
"""

from datetime import timedelta
from zoneinfo import ZoneInfo

TARGET = "energinet.dk1.satisfied_demand"
DIRECTION = "energinet.dk1.dominating_direction"
ISP = timedelta(minutes=15)
LOOKBACK = timedelta(days=7)  # volume: persistence band and the ar(1) fit
CLIMATE = timedelta(days=28)  # direction: by Copenhagen hour
COPENHAGEN = ZoneInfo("Europe/Copenhagen")
CODE = {1: "up", -1: "down", 0: "none"}


class MissingData(Exception):
    pass


def _known(history, series_id, asof, span):
    values = history(series_id, asof - span, asof, asof)
    if not values:
        raise MissingData(f"{series_id}: nothing known in the {span} before {asof}")
    return values


def _last(values, asof, max_age=timedelta(hours=2)):
    isp = max(values)
    if asof - isp > max_age:
        raise MissingData(f"latest known ISP {isp} is stale at {asof}")
    return isp, float(values[isp])


def _steps(last_isp, target):
    return round((target - last_isp) / ISP)


def _quantile(xs, q):
    xs = sorted(xs)
    i = q * (len(xs) - 1)
    lo, hi = int(i), min(int(i) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def _k_step_changes(values, k):
    return [
        float(values[t + k * ISP]) - float(values[t])
        for t in values
        if t + k * ISP in values
    ]


def persistence(history, target, asof):
    """The latest known ISP, with a band from 7 days of same-gap changes."""
    values = _known(history, TARGET, asof, LOOKBACK)
    last_isp, last = _last(values, asof)
    k = _steps(last_isp, target)
    changes = _k_step_changes(values, k)
    if len(changes) < 96:
        raise MissingData(f"only {len(changes)} {k}-step changes to build a band")
    return {
        "point": last,
        "q10": last + _quantile(changes, 0.1),
        "q50": last,
        "q90": last + _quantile(changes, 0.9),
        "steps": k,
    }


def persistence_ar1(history, target, asof):
    """Mean reversion: mu + phi^k (last - mu), phi and mu fitted on 7 days."""
    values = _known(history, TARGET, asof, LOOKBACK)
    last_isp, last = _last(values, asof)
    k = _steps(last_isp, target)
    pairs = [
        (float(values[t]), float(values[t + ISP])) for t in values if t + ISP in values
    ]
    if len(pairs) < 96:
        raise MissingData(f"only {len(pairs)} pairs to fit ar(1)")
    mu = sum(x for x, _ in pairs) / len(pairs)
    sxx = sum((x - mu) ** 2 for x, _ in pairs)
    phi = sum((x - mu) * (y - mu) for x, y in pairs) / sxx if sxx else 0.0
    phi = min(max(phi, 0.0), 1.0)
    point = mu + phi**k * (last - mu)
    resid = [
        float(values[t + k * ISP]) - (mu + phi**k * (float(values[t]) - mu))
        for t in values
        if t + k * ISP in values
    ]
    return {
        "point": point,
        "q10": point + _quantile(resid, 0.1),
        "q50": point,
        "q90": point + _quantile(resid, 0.9),
        "steps": k,
        "phi": round(phi, 4),
    }


def _probabilities(counts):
    """Rounded to 4 decimals with p_none taking the remainder, so they sum to 1."""
    total = sum(counts.values())
    p_up = round(counts["up"] / total, 4)
    p_down = round(counts["down"] / total, 4)
    return {"p_up": p_up, "p_down": p_down, "p_none": round(1 - p_up - p_down, 4)}


def _call(probs):
    return max(("up", "down", "none"), key=lambda k: probs[f"p_{k}"])


def direction_persistence(history, target, asof):
    """The latest known ISP's direction, with all its probability."""
    values = _known(history, DIRECTION, asof, LOOKBACK)
    _, last = _last(values, asof)
    probs = {f"p_{v}": float(CODE[int(last)] == v) for v in ("up", "down", "none")}
    return {**probs, "direction": CODE[int(last)]}


def direction_climatology(history, target, asof):
    """How often each direction happened at the target's Copenhagen hour over
    the last 28 days, with one added to each so none is ever zero."""
    values = _known(history, DIRECTION, asof, CLIMATE)
    hour = target.astimezone(COPENHAGEN).hour
    counts = {"up": 1, "down": 1, "none": 1}
    for t, v in values.items():
        if t.astimezone(COPENHAGEN).hour == hour:
            counts[CODE[int(v)]] += 1
    if sum(counts.values()) < 3 + 14:
        raise MissingData(f"fewer than 14 days of direction at {hour}:00")
    probs = _probabilities(counts)
    return {**probs, "direction": _call(probs)}
