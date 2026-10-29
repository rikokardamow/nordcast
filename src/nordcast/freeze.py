"""Freeze the calls for one ISP and horizon before it's due.

Rows only: each is hashed (sha256 of its canonical JSON) and written in one
transaction; the day's rows go into one stamped file later
(jobs/stamp_daily.py). The database refuses a row after the ISP's deadline.

Per ISP and horizon:
  model     the headline call. v0 is persistence (volume and direction)
            until a model earns the call at a quarter boundary.
  baseline  persistence (the bar), persistence_ar1 (volume),
            direction_climatology (direction).
  challenger  models building a live record before any promotion
            (nordcast.challenger). One that fails writes no row; its miss
            is reported by the job and counts against it.
If the model fails, persistence is frozen in its place, flagged. If
persistence itself can't be built, nothing is frozen and the job fails.
"""

import hashlib
import json
from datetime import timedelta

import psycopg

from nordcast import baselines, store

SERIES = baselines.TARGET
HORIZONS = (15, 30, 60)  # minutes before the ISP starts


class AlreadyFrozen(Exception):
    pass


def _history(conn):
    def history(series_id, from_ts, to_ts, asof):
        return store.history_asof(conn, series_id, from_ts, to_ts, asof)

    return history


def persistence_call(history, target, asof):
    return {
        **baselines.persistence(history, target, asof),
        **baselines.direction_persistence(history, target, asof),
    }


def v0_model(history, target, asof):
    return {
        **persistence_call(history, target, asof),
        "model_version": "v0-persistence",
    }


def _mw(x):
    return None if x is None else f"{float(x):.1f}"


def _p(x):
    return None if x is None else f"{float(x):.4f}"


def _probabilities(call):
    """p_up and p_down at 4 decimals, p_none the remainder, so the three add up
    to exactly 1; rounding each on its own can miss by more than the
    database's 0.0001 and refuse the row (20:00/h30, 29 Oct 2026)."""
    if call.get("p_up") is None:
        return {"p_up": None, "p_down": None, "p_none": None}
    up = round(float(call["p_up"]), 4)
    down = min(round(float(call["p_down"]), 4), round(1 - up, 4))  # never p_none < 0
    return {"p_up": _p(up), "p_down": _p(down), "p_none": _p(1 - up - down)}


def make_row(release, target, horizon, cutoff, source_kind, method, status, call):
    payload = {
        "release": f"{release['kind']} {release['scheduled_at'].isoformat()}",
        "series_id": SERIES,
        "target_period": target.isoformat(),
        "horizon_min": horizon,
        "source_kind": source_kind,
        "method": method,
        "status": status,
        "point": _mw(call.get("point")),
        "q10": _mw(call.get("q10")),
        "q50": _mw(call.get("q50")),
        "q90": _mw(call.get("q90")),
        "direction": call.get("direction"),
        **_probabilities(call),
        "data_cutoff": cutoff.isoformat(),
        "model_version": call.get("model_version"),
        "flag_reason": call.get("flag_reason"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    return payload


INSERT = (
    "insert into forecast (release_id, series_id, target_period, horizon_min,"
    " source_kind, method, status, point, q10, q50, q90, direction, p_up, p_down,"
    " p_none, data_cutoff, model_version, flag_reason, sha256, payload)"
    " values (%(release_id)s, %(series_id)s, %(target_period)s, %(horizon_min)s,"
    " %(source_kind)s, %(method)s, %(status)s, %(point)s, %(q10)s, %(q50)s,"
    " %(q90)s, %(direction)s, %(p_up)s, %(p_down)s, %(p_none)s, %(data_cutoff)s,"
    " %(model_version)s, %(flag_reason)s, %(sha256)s, %(payload)s)"
)


def insert(conn, release_id, row):
    params = {**row, "release_id": release_id, "payload": json.dumps(row)}
    try:
        conn.execute(INSERT, params)
    except psycopg.errors.UniqueViolation as exc:
        raise AlreadyFrozen(
            f"{row['target_period']} h{row['horizon_min']} {row['method']}"
        ) from exc


def make_calls(history, target, now, model=v0_model, horizon=None, challengers=(),
               missed=None):  # fmt: skip
    """[(source_kind, method, status, call)] for one ISP, computed, not written.

    challengers: (method, fn(history, target, now, horizon)). A failure is
    appended to `missed` as "method: error" and never blocks the other calls."""
    bar = persistence_call(history, target, now)  # MissingData here fails the freeze
    try:
        call, status = model(history, target, now), "frozen"
    except Exception as exc:  # noqa: BLE001 - any model failure falls back
        call = {**bar, "flag_reason": f"model failed: {type(exc).__name__}"}
        status = "auto_baseline"
    calls = [
        ("model", "model", status, call),
        ("baseline", "persistence", "frozen", bar),
    ]
    for method, fn in (
        ("persistence_ar1", baselines.persistence_ar1),
        ("direction_climatology", baselines.direction_climatology),
    ):
        try:
            calls.append(("baseline", method, "frozen", fn(history, target, now)))
        except baselines.MissingData:
            pass  # a secondary baseline never blocks the bar or the model
    for method, fn in challengers:
        try:
            call = fn(history, target, now, horizon)
            calls.append(("challenger", method, "frozen", call))
        except Exception as exc:  # noqa: BLE001
            if missed is not None:
                missed.append(f"{method}: {type(exc).__name__}: {exc}"[:200])
    return calls


def freeze_rows(conn, release, horizon, now, model=v0_model, challengers=(),
                missed=None):  # fmt: skip
    """Freeze every call for `release` (the ISP) at `horizon`. Returns the rows."""
    release_id, target, due = release
    if target - now < timedelta(minutes=horizon):
        raise ValueError(f"{target} is less than {horizon} min away at {now}")
    meta = {"kind": "dk1_isp", "scheduled_at": due}
    rows = [
        make_row(meta, target, horizon, now, kind, method, status, call)
        for kind, method, status, call in make_calls(
            _history(conn), target, now, model, horizon, challengers, missed
        )
    ]
    written = []
    with conn.transaction():
        for r in rows:
            if r["source_kind"] != "challenger":
                insert(conn, release_id, r)
                written.append(r)
                continue
            try:
                with (
                    conn.transaction()
                ):  # a savepoint: a challenger never blocks the rest
                    insert(conn, release_id, r)
                written.append(r)
            except Exception as exc:  # noqa: BLE001
                if missed is not None:
                    missed.append(f"{r['method']}: {type(exc).__name__}: {exc}"[:200])
    return written
