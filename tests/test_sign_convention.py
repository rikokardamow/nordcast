"""Pins Energinet's sign: positive SatisfiedDemand is up-regulation.

Checked on every ISP since 4 Mar 2025 (notes/sources.md); this re-checks a
fixed week against the live API, so a silent change at Energinet fails CI
instead of the record. Skips only when the API can't be reached.
"""

import httpx
import pytest

WEEK = {"start": "2026-10-19T00:00", "end": "2026-10-26T00:00"}


@pytest.fixture(scope="module")
def week():
    try:
        r = httpx.get(
            "https://api.energidataservice.dk/dataset/ImbalancePrice",
            params={**WEEK, "filter": '{"PriceArea":["DK1"]}', "limit": 0},
            timeout=60,
        )
        r.raise_for_status()
    except httpx.HTTPError as exc:
        pytest.skip(f"Energi Data Service unreachable: {exc}")
    return r.json()["records"]


def test_positive_satisfied_demand_is_up(week):
    directional = [r for r in week if r["DominatingDirection"] in (1, -1)]
    assert len(directional) > 400
    agree = sum(
        (r["SatisfiedDemand"] > 0) == (r["DominatingDirection"] == 1)
        for r in directional
    )
    assert agree / len(directional) > 0.99


def test_direction_is_coded_1_0_minus_1(week):
    assert {r["DominatingDirection"] for r in week} <= {1, 0, -1}
