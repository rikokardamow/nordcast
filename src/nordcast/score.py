"""Score every frozen call for an ISP against the first print.

Volume: the first published SatisfiedDemand for the ISP. Direction: the
first published DominatingDirection. Later revisions are kept as vintages
but never change a score.
"""

from datetime import timedelta

from nordcast import quality, store
from nordcast.baselines import CODE, DIRECTION, TARGET

LOOKBACK = timedelta(days=7)
QUANTILES = (("q10", 0.1), ("q50", 0.5), ("q90", 0.9))


def first_print_at(conn, series_id, isp):
    return conn.execute(
        "select min(published_at) from observation"
        " where series_id = %s and observed_for = %s",
        (series_id, isp),
    ).fetchone()[0]


def pinball(q, tau, actual):
    return max(tau * (actual - q), (tau - 1) * (actual - q))


def brier(f, direction):
    return sum(
        (float(f[f"p_{k}"]) - (k == direction)) ** 2 for k in ("up", "down", "none")
    )


def losses(f, actual, direction):
    """Every loss for one forecast row (a dict of its columns)."""
    out = {"error": None, "abs_error": None, "covered": None}
    out |= {f"pinball_{name}": None for name, _ in QUANTILES}
    out |= {"direction_hit": None, "brier": None}
    if f["point"] is not None:
        out["error"] = float(f["point"]) - actual
        out["abs_error"] = abs(out["error"])
    for name, tau in QUANTILES:
        if f[name] is not None:
            out[f"pinball_{name}"] = pinball(float(f[name]), tau, actual)
    if f["q10"] is not None and f["q90"] is not None:
        out["covered"] = float(f["q10"]) <= actual <= float(f["q90"])
    if f["direction"] is not None:
        out["direction_hit"] = f["direction"] == direction
        out["brier"] = brier(f, direction)
    return out


INSERT = (
    "insert into score (forecast_id, actual, error, abs_error, first_print_at,"
    " outlier, direction_actual, direction_hit, brier, pinball_q10, pinball_q50,"
    " pinball_q90, covered) values (%(forecast_id)s, %(actual)s, %(error)s,"
    " %(abs_error)s, %(first_print_at)s, %(outlier)s, %(direction_actual)s,"
    " %(direction_hit)s, %(brier)s, %(pinball_q10)s, %(pinball_q50)s,"
    " %(pinball_q90)s, %(covered)s) on conflict (forecast_id) do nothing"
)


def score_isp(conn, isp, now):
    """Returns ('pending' | 'scored', rows written)."""
    if now < isp + timedelta(minutes=15):
        return "pending", 0
    fp = first_print_at(conn, TARGET, isp)
    dfp = first_print_at(conn, DIRECTION, isp)
    if fp is None or dfp is None:
        return "pending", 0
    actual = float(store.value_asof(conn, TARGET, isp, fp))
    direction = CODE[int(store.value_asof(conn, DIRECTION, isp, dfp))]
    past = store.history_asof(conn, TARGET, isp - LOOKBACK, isp, fp)
    outlier = quality.is_outlier(actual, [float(v) for v in past.values()])

    cols = (
        "forecast_id",
        "point",
        "q10",
        "q50",
        "q90",
        "direction",
        "p_up",
        "p_down",
        "p_none",
    )
    forecasts = conn.execute(
        f"select {', '.join('f.' + c for c in cols)} from forecast f"
        " join release r using (release_id)"
        " where r.release_kind = 'dk1_isp' and r.period_end = %s",
        (isp,),
    ).fetchall()
    written = 0
    for row in forecasts:
        f = dict(zip(cols, row, strict=True))
        params = {
            "forecast_id": f["forecast_id"],
            "actual": actual,
            "first_print_at": fp,
            "outlier": outlier,
            "direction_actual": direction,
            **losses(f, actual, direction),
        }
        written += conn.execute(INSERT, params).rowcount
    return "scored", written
