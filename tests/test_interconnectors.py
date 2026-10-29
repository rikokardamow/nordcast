"""Pins layer #33: each DK1 border's flow from the 5-min feed matches
settlement's exchange for that border (+ = import), on a fixed week against
the live API, so a sign flip or renamed column fails CI. Skips only when the
API can't be reached.
"""

import statistics
from collections import defaultdict
from datetime import UTC, datetime

import httpx
import pytest

from nordcast.sources import energinet

WEEK = {"start": "2026-10-01T00:00", "end": "2026-10-08T00:00"}
BORDERS = {
    "de": "ExchangeGE_MWh",
    "nl": "ExchangeNL_MWh",
    "gb": "ExchangeGB_MWh",
    "no": "ExchangeNO_MWh",
    "se": "ExchangeSE_MWh",
    "dk2": "ExchangeGreatBelt_MWh",
}


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


@pytest.fixture(scope="module")
def week():
    return _get("ElectricityProdex5MinRealtime"), _get(
        "ProductionConsumptionSettlement"
    )


@pytest.mark.parametrize("border", BORDERS)
def test_flow_matches_settlement_and_imports_are_positive(week, border):
    realtime, settlement = week
    spec = energinet.SERIES[f"energinet.dk1.flow_{border}_mw"]
    per_hour = defaultdict(list)
    for isp, v in energinet.isp_values(spec, realtime).items():
        per_hour[isp.replace(minute=0)].append(v)
    settled = {
        datetime.fromisoformat(r["HourUTC"]).replace(tzinfo=UTC): r[BORDERS[border]]
        for r in settlement
    }
    pairs = [
        (sum(v) / 4, settled[h])
        for h, v in per_hour.items()
        if len(v) == 4 and settled.get(h) is not None
    ]
    assert len(pairs) > 160
    ours, theirs = zip(*pairs)
    assert statistics.correlation(ours, theirs) > 0.99
    assert abs(statistics.mean(o - t for o, t in pairs)) < 50  # MW
