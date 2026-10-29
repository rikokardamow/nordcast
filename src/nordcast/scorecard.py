"""The readme's scorecard, computed from the scored record.

One line per horizon for the headline and for each challenger. The three
skill columns are the pre-registered statistics (notes/preregistration.md,
with amendment 1): pinball against persistence, Brier against persistence,
and Brier against direction_climatology. Each is, per ISP, d = loss(bar) -
loss(method), averaged per Copenhagen day, and the mean daily d with a
day-block bootstrap 90 % interval (10,000 draws, seed 20261029). A
challenger's missing call is filled with persistence's loss, against either
bar, so a miss never helps it. Positive is better than the bar.

Standard library only, so it runs in the plain job environment.
"""

import random
import re
from collections import defaultdict
from datetime import timedelta
from zoneinfo import ZoneInfo

COPENHAGEN = ZoneInfo("Europe/Copenhagen")
HORIZONS = (15, 30, 60)
DRAWS = 10_000
SEED = 20261029
START, END = "<!-- scorecard -->", "<!-- /scorecard -->"

QUERY = (
    "select r.period_end, f.horizon_min, f.source_kind, f.method,"
    " (s.pinball_q10 + s.pinball_q50 + s.pinball_q90) / 3, s.brier,"
    " s.direction_hit, s.covered"
    " from forecast f join release r using (release_id)"
    " join score s using (forecast_id)"
    " where s.status = 'scored' and r.release_kind = 'dk1_isp'"
)


def bootstrap(daily, draws=DRAWS, seed=SEED):
    """(mean, 5th, 95th percentile) of the mean of `daily`, resampling days."""
    if not daily:
        return None
    rng = random.Random(seed)
    n = len(daily)
    means = sorted(sum(rng.choices(daily, k=n)) / n for _ in range(draws))
    return sum(daily) / n, means[int(0.05 * draws)], means[int(0.95 * draws) - 1]


def skill(bar, method, fill=None):
    """bar, method, fill: {isp: loss}. Mean daily d with its interval. A
    missing call takes `fill`'s loss (persistence's; the bar's own if None);
    an ISP with neither is left out."""
    by_day = defaultdict(list)
    for isp, loss_bar in bar.items():
        if loss_bar is None:
            continue
        loss = method.get(isp)
        if loss is None:
            loss = loss_bar if fill is None else fill.get(isp)
        if loss is None:
            continue
        d = float(loss_bar) - float(loss)
        by_day[isp.astimezone(COPENHAGEN).date()].append(d)
    return bootstrap([sum(v) / len(v) for _, v in sorted(by_day.items())])


def lines(rows, due):
    """rows: QUERY's rows. due: {horizon: calls due so far}. -> table dicts."""
    calls = defaultdict(dict)  # (h, label) -> {isp: row}
    for isp, h, kind, method, pinball, brier, hit, covered in rows:
        if kind == "model":
            label = "headline"
        elif kind == "challenger":
            label = f"{method} (challenger)"
        elif method == "persistence":
            label = "bar"
        elif method == "direction_climatology":
            label = "climatology"
        else:
            continue
        calls[(h, label)][isp] = (pinball, brier, hit, covered)
    out = []
    for h in HORIZONS:
        pers = calls.get((h, "bar"), {})
        bar = {isp: v[0] for isp, v in pers.items()}
        bar_brier = {isp: v[1] for isp, v in pers.items()}
        clim = {isp: v[1] for isp, v in calls.get((h, "climatology"), {}).items()}
        for (hh, label), got in sorted(calls.items()):
            if hh != h or label in ("bar", "climatology"):
                continue
            brier = {i: v[1] for i, v in got.items()}
            hits = [v[2] for v in got.values() if v[2] is not None]
            cov = [v[3] for v in got.values() if v[3] is not None]
            out.append(
                {
                    "horizon": h,
                    "method": label,
                    "calls": len(got),
                    "direction_hit": sum(hits) / len(hits) if hits else None,
                    "skill": skill(bar, {i: v[0] for i, v in got.items()}),
                    "brier_vs_persistence": skill(bar_brier, brier),
                    "brier_vs_climatology": skill(clim, brier, fill=bar_brier),
                    "coverage": sum(cov) / len(cov) if cov else None,
                    "on_time": len(got) / due[h] if due.get(h) else None,
                    "since": min(got).astimezone(COPENHAGEN).date(),
                }
            )
    return out


def _pct(x):
    return "–" if x is None else f"{100 * x:.1f} %"


def _skill(s):
    return "–" if s is None else f"{s[0]:+.1f} MW ({s[1]:+.1f} to {s[2]:+.1f})"


def _brier(s):
    return "–" if s is None else f"{s[0]:+.3f} ({s[1]:+.3f} to {s[2]:+.3f})"


def markdown(table):
    head = (
        "| horizon | method | calls | direction hit | pinball vs persistence"
        " (90 % CI) | Brier vs persistence | Brier vs climatology"
        " | coverage q10–q90 | on-time | live since |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
    )
    if not table:
        return head + "| – | no scored calls yet | – | – | – | – | – | – | – | – |\n"
    return head + "".join(
        f"| {r['horizon']} min | {r['method']} | {r['calls']:,} |"
        f" {_pct(r['direction_hit'])} | {_skill(r['skill'])} |"
        f" {_brier(r['brier_vs_persistence'])} | {_brier(r['brier_vs_climatology'])} |"
        f" {_pct(r['coverage'])} | {_pct(r['on_time'])} | {r['since']:%-d %b %Y} |\n"
        for r in table
    )


def replace(readme, table_md):
    """The readme with the text between the markers swapped for `table_md`."""
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(readme):
        raise ValueError(f"readme has no {START} ... {END} block")
    return pattern.sub(lambda _: f"{START}\n{table_md}{END}", readme)


def due_since(conn, now):
    """{horizon: calls whose freeze window has passed since the first freeze}."""
    first = conn.execute(
        "select min(r.period_end) from forecast f join release r using (release_id)"
        " where f.source_kind = 'model'"
    ).fetchone()[0]
    if first is None:
        return {}
    out = {}
    for h in HORIZONS:
        (out[h],) = conn.execute(
            "select count(*) from release where release_kind = 'dk1_isp'"
            " and period_end >= %s and period_end - %s <= %s",
            (first, timedelta(minutes=h), now),
        ).fetchone()
    return out
