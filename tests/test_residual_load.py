"""Pins layer #32: residual load from the 5-min feed equals settlement's
thermal production + net import, so the exchange sign (+ = import) and the
column set hold. Re-checks a fixed week against the live API, so a silent
change at Energinet fails CI; skips only when the API can't be reached.
"""

import statistics
from collections import defaultdict
from datetime import UTC, datetime

import httpx
import pytest

from nordcast.sources import energinet

SID = "energinet.dk1.residual_load_mw"
WEEK = {"start": "2026-10-01T00:00", "end": "2026-10-08T00:00"}
SETTLED = ("CentralPowerMWh", "LocalPowerMWh", "CommercialPowerMWh", "HydroPowerMWh",
           "UnknownProdMWh", "ExchangeNO_MWh", "ExchangeSE_MWh", "ExchangeGE_MWh",
           "ExchangeNL_MWh", "ExchangeGB_MWh", "ExchangeGreatBelt_MWh")  # fmt: skip


def _get(dataset):
    try:
        r = httpx.get(
            f"https://api.energidataservice.dk/dataset/{dataset}",
            params={**WEEK, "filter": '{"PriceArea":["DK1"]}', "limit": 0},
            timeout=60,
        )
        r.raise_for_status()
    except httpx.HTTPError as exc:
        pytest.skip(f"Energi Data Service unreachable: {exc}")
    return r.json()["records"]


def test_isp_value_adds_imports_and_thermal_only():
    spec = energinet.SERIES[SID]
    row = {c: 0.0 for c in spec.columns} | {"ProductionGe100MW": 500.0,
           "ExchangeGermany": -200.0, "OnshoreWindPower": 3000.0}  # fmt: skip
    records = [{**row, "Minutes5UTC": f"2026-10-01T00:{m:02d}:00"} for m in (0, 5, 10)]
    isp = datetime(2026, 10, 1, tzinfo=UTC)
    assert energinet.isp_values(spec, records) == {isp: 300.0}  # wind not in it


def test_residual_load_matches_settlement_hourly():
    spec = energinet.SERIES[SID]
    per_hour = defaultdict(list)
    for v_isp, v in energinet.isp_values(
        spec, _get("ElectricityProdex5MinRealtime")
    ).items():
        per_hour[v_isp.replace(minute=0)].append(v)
    settled = {
        datetime.fromisoformat(r["HourUTC"]).replace(tzinfo=UTC): sum(
            r[c] or 0 for c in SETTLED
        )
        for r in _get("ProductionConsumptionSettlement")
    }
    pairs = [
        (sum(v) / 4, settled[h])
        for h, v in per_hour.items()
        if len(v) == 4 and h in settled
    ]
    assert len(pairs) > 160
    ours, theirs = zip(*pairs)
    assert statistics.correlation(ours, theirs) > 0.99
    assert abs(statistics.mean(o - t for o, t in pairs)) < 100  # MW
