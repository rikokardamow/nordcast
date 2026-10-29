"""Check every measurable nominal lag against the archive's first prints.

    uv run --all-groups python docs/experiments/first-print-lags/run.py

Backfilled history is stamped published_at = NOMINAL_LAG(isp), and the
challenger reads live data through the same lags (challenger.nominal). A lag
must err late: a value really published after its nominal time would let
training see it earlier than live can (notes/backfill.md: "if it isn't, the
lag constant is wrong").

The archive (~/nordcast-archive) keeps every pull with pulled_at_utc. For each
series from an archived dataset, an ISP's first print is the first pull in
which the ISP's value is complete (every 5-min piece non-null). pulled_at is
at or after the real publication, so first print <= nominal proves the lag
safe; first print > nominal by more than the pull interval proves it unsafe.

Only ISPs the archive watched throughout are kept: no gap over 6 min between
pulls of that dataset from the ISP's start to 30 min past the series'
nominal lag (a late first print within that would be seen). Pull
times come from the archive's log (one line per source per run, stamped
with the run's pulled_at), since a pull that adds nothing writes no row.
Forecast series (the archive keeps a 2-hour window, not their issue time) and
day-ahead prices (not archived) can't be checked here.
"""

from collections import defaultdict
from datetime import timedelta
from itertools import pairwise
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from nordcast.sources import energinet

HERE = Path(__file__).parent
ARCHIVE = Path.home() / "nordcast-archive"
LOG = Path.home() / "Library" / "Logs" / "nordcast" / "nordcast.archive.log"
FOLDER = {
    "ImbalancePrice": "imbalance_price",
    "MfrrEnergyActivationMarket": "mfrr_activation",
    "ElectricityProdex5MinRealtime": "prodex_5min",
}
ISP = timedelta(minutes=15)
SLACK = timedelta(minutes=30)
MAX_GAP = timedelta(minutes=6)


def rows(folder):
    out = []
    for p in sorted((ARCHIVE / folder).glob("*.parquet")):
        out += [r for r in pq.read_table(p).to_pylist() if r.get("PriceArea") == "DK1"]
    return out


def pull_times(folder):
    """Every successful pull of `folder` in the archive's log."""
    out = []
    for line in LOG.read_text().splitlines():
        ts, _, rest = line.partition(" ")
        if rest.startswith(f"{folder}: +"):
            out.append(pd.Timestamp(ts).to_pydatetime())
    return out


def watched(pulls):
    """f(start, end): True if no gap over MAX_GAP between pulls in [start, end]."""
    pulls = sorted(set(pulls))

    def ok(start, end):
        inside = [p for p in pulls if start - MAX_GAP <= p <= end + MAX_GAP]
        if not inside or inside[0] > start or inside[-1] < end:
            return False
        return all(b - a <= MAX_GAP for a, b in pairwise(inside))

    return ok


def first_prints(spec, recs):
    """{isp: first pulled_at at which the ISP's value was complete}."""
    seen = defaultdict(lambda: None)  # 5-min (or ISP) time -> first complete pull
    for r in sorted(recs, key=lambda r: r["pulled_at_utc"]):
        vals = [r.get(c) for c in spec.columns]
        if any(v is None for v in vals):
            continue
        t = energinet._utc(r[spec.time_col])
        if seen[t] is None:
            seen[t] = r["pulled_at_utc"]
    per_isp = defaultdict(list)
    for t, p in seen.items():
        per_isp[energinet._isp_start(t)].append(p)
    n = 15 // spec.resolution_min
    return {isp: max(ps) for isp, ps in per_isp.items() if len(ps) == n}


def main():
    lines = []
    for dataset, folder in FOLDER.items():
        recs = rows(folder)
        ok = watched(pull_times(folder))
        specs = {sid: s for sid, s in energinet.SERIES.items() if s.dataset == dataset}
        for sid, spec in specs.items():
            fp = first_prints(spec, recs)
            d = pd.DataFrame(
                [(isp, p) for isp, p in fp.items() if ok(isp, spec.lag(isp) + SLACK)],
                columns=["isp", "first"],
            )
            if d.empty:
                lines.append({"series": sid, "isps": 0})
                continue
            d["after_end_min"] = (d["first"] - (d.isp + ISP)).dt.total_seconds() / 60
            d["nominal_after_end_min"] = d.isp.map(
                lambda t, lag=spec.lag: (lag(t) - (t + ISP)).total_seconds() / 60
            )
            late = d["first"] > d.isp.map(spec.lag)
            lines.append({
                "series": sid,
                "isps": len(d),
                "from": d.isp.min(),
                "to": d.isp.max(),
                "nominal_min": float(d.nominal_after_end_min.median()),
                "first_print_p50_min": float(d.after_end_min.median()),
                "p95_min": float(d.after_end_min.quantile(0.95)),
                "max_min": float(d.after_end_min.max()),
                "share_after_nominal": float(late.mean()),
            })  # fmt: skip
    table = pd.DataFrame(lines)
    table.to_csv(HERE / "results.csv", index=False, float_format="%.2f")
    print(table.to_string(index=False, float_format=lambda x: f"{x:.1f}"))


if __name__ == "__main__":
    main()
