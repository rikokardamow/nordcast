"""Layer #31 (DK1 part): day-ahead price coupling with DK1's neighbours, checked
against the physical flows (#33), and tested as an input to the imbalance call.

    uv run --all-groups python docs/layers/price-coupling/backtest.py

Prices: DayAheadPrices for DE, DK1, DK2, NO2, SE3, cached per month in
data/history/DayAheadPricesAll/ (gitignored), outside the record. Spread =
DK1 - neighbour, EUR/MWh; "coupled" = |spread| < 0.01.

1. Coupling check, 1 Oct 2025 - 28 Oct 2026, per border with a price:
   share coupled; share of ISPs at the observed limit (#33) when coupled and
   when split; and, on split ISPs, how often the physical flow runs toward
   the dearer side (import when DK1 is dearer).
2. Alpha test: the target ISP's spreads are published the day before, so they
   are known at every freeze. Features: the four spreads and n_split.
   Weekly refit out of sample on the replay's 2026 rounds, as in #32/#33:
     base vs base+pc (rung 4), rl vs rl+pc (rung 4 + residual load).
"""

import importlib.util
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pandas as pd
import psycopg

HERE = Path(__file__).parent
CACHE = HERE.parents[2] / "data" / "history" / "DayAheadPricesAll"
AREAS = ("DK1", "DE", "DK2", "NO2", "SE3")
BORDER = {"DE": "de", "DK2": "dk2", "NO2": "no", "SE3": "se"}  # price area -> #33 flow
PCF = ["spread_de", "spread_dk2", "spread_no2", "spread_se3", "n_split"]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ic = _load("ic_bt", HERE.parent / "interconnectors" / "backtest.py")
rl_bt, replay, features = ic.rl_bt, ic.replay, ic.features


def month_prices(first, client):
    path = CACHE / f"{first:%Y-%m}.parquet"
    now = datetime.now(UTC)
    if path.exists() and (first.year, first.month) != (now.year, now.month):
        return pd.read_parquet(path)
    nxt = (first + pd.offsets.MonthBegin(1)).to_pydatetime()
    for _ in range(5):  # 429: wait a minute, as energinet.fetch does
        r = client.get(
            "https://api.energidataservice.dk/dataset/DayAheadPrices",
            params={
                "start": f"{first:%Y-%m-%dT%H:%M}",
                "end": f"{nxt:%Y-%m-%dT%H:%M}",
                "filter": '{"PriceArea":' + str(list(AREAS)).replace("'", '"') + "}",
                "timezone": "UTC",
                "limit": 0,
            },
        )
        if r.status_code != 429:
            break
        time.sleep(60)
    r.raise_for_status()
    df = pd.DataFrame(r.json()["records"])[["TimeUTC", "PriceArea", "DayAheadPriceEUR"]]
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    time.sleep(5)  # the archive shares this per-IP limit
    return df


def prices():
    months = pd.date_range(
        "2025-10-01", datetime.now(UTC).replace(tzinfo=None), freq="MS"
    )
    with httpx.Client(timeout=120) as client:
        raw = pd.concat([month_prices(m.to_pydatetime(), client) for m in months])
    raw["t"] = pd.to_datetime(raw.TimeUTC).dt.tz_localize("UTC")
    p = raw.pivot_table(index="t", columns="PriceArea", values="DayAheadPriceEUR")
    out = pd.DataFrame(index=p.index)
    for area in BORDER:
        out[f"spread_{area.lower()}"] = p["DK1"] - p[area]
    out["n_split"] = (out.abs() >= 0.01).sum(axis=1)
    return out


def coupling_check(spreads, flows):
    w = spreads.join(flows, how="inner").loc["2025-10-01":"2026-10-28"]
    lines = []
    for area, b in BORDER.items():
        s, f = w[f"spread_{area.lower()}"], w[b]
        hi = f.clip(lower=0).rolling("28D").max()
        lo = f.clip(upper=0).rolling("28D").min()
        at = ((f > 0) & (f >= ic.LIMIT * hi)) | ((f < 0) & (f <= ic.LIMIT * lo))
        coupled = s.abs() < 0.01
        split = ~coupled & (f.abs() > 1)
        toward_dear = (f[split] > 0) == (s[split] > 0)  # import when DK1 is dearer
        lines.append({
            "border": f"DK1-{area}", "isps": len(s.dropna()),
            "coupled": coupled.mean(), "coupled_within_0.5": (s.abs() < 0.5).mean(),
            "at_limit_when_coupled": at[coupled].mean(),
            "at_limit_when_split": at[~coupled].mean(),
            "flow_toward_dearer_when_split": toward_dear.mean(),
            "mean_abs_spread": s.abs().mean(),
        })  # fmt: skip
    return pd.DataFrame(lines)


def main():
    spreads = prices()
    with psycopg.connect(ic.DB_URL) as conn:
        frame = ic.isp_frame(conn)
    check = coupling_check(spreads, frame[list(BORDER.values())])
    check.to_csv(HERE / "coupling.csv", index=False, float_format="%.3f")
    print(check.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print("all four coupled:", f"{(spreads.n_split == 0).mean():.1%}")

    out = []
    for h in (15, 30, 60):
        every = pd.read_parquet(f"data/training/h{h}.parquet").sort_values("target")
        every = every.join(ic.known_at(frame, every.target, h))
        every = every.join(
            spreads.reindex(every.target.to_numpy()).set_axis(every.index)
        )
        every = every.dropna(subset=PCF + ic.RLF + replay.LINEAR_LAGS)
        for name in rl_bt.ROUNDS:
            start, end = replay.ROUNDS[name]
            rows = every[(every.target >= start) & (every.target < end)]
            pred = {
                k: rl_bt.fit_predict(rows, every, cols)
                for k, cols in (
                    ("base", []),
                    ("base+pc", PCF),
                    ("rl", ic.RLF),
                    ("rl+pc", ic.RLF + PCF),
                )
            }
            err = {k: p - rows.y for k, p in pred.items()}
            row = {"h": h, "round": name, "n": len(rows)}
            row |= {f"mae_{k}": float(e.abs().mean()) for k, e in err.items()}
            for a, b in (("base", "base+pc"), ("rl", "rl+pc")):
                g = rl_bt.gain(rows, err[a], err[b])
                row |= {f"{b}_{k}": v for k, v in g.items()}
            out.append(row)
            print({k: round(v, 3) if isinstance(v, float) else v for k, v in row.items()
                   if k.endswith(("gain_mw", "_lo", "_hi", "_t")) or k in ("h", "round")},
                  flush=True)  # fmt: skip
    pd.DataFrame(out).to_csv(HERE / "backtest.csv", index=False, float_format="%.3f")


if __name__ == "__main__":
    main()
