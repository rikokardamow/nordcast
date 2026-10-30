"""Pins what Energinet says the columns we read mean.

Energinet has changed the data under us twice with only a metadata note: the
imbalance columns left PowerSystemRightNow, and SatisfiedDemand went from
demand to activated on 4 Mar 2026. ops/run_jobs.sh runs this hourly, on this
machine. Cautions aren't pinned; they list routine outages.

On a failure, read the change. If the target's meaning moved, the regime-break
rule in notes/preregistration.md applies. Then re-pin:
    uv run python tests/test_eds_definitions.py

Skips only when the API can't be reached; a missing dataset fails.
"""

import json
from pathlib import Path

import httpx
import pytest

from nordcast.sources import energinet

PINNED = Path(__file__).parent / "data" / "eds-definitions.json"
FIELDS = ("dataType", "unit", "description", "comment")


def used_columns():
    used = {d: set() for d in energinet.DATASETS}
    for s in energinet.SERIES.values():
        used[s.dataset] |= {s.time_col, *s.columns}
    return used


def definitions(dataset, columns):
    r = httpx.get(
        f"https://api.energidataservice.dk/meta/dataset/{dataset}", timeout=30
    )
    if r.status_code == 429 or r.status_code >= 500:
        raise httpx.TransportError(f"HTTP {r.status_code}")
    r.raise_for_status()
    return {
        f"{dataset}.{c['dbColumn']}": {f: " ".join(str(c[f]).split()) for f in FIELDS}
        for c in r.json()["columns"]
        if c["dbColumn"] in columns
    }


def live_definitions():
    live = {}
    for dataset, columns in used_columns().items():
        live |= definitions(dataset, columns)
    return live


@pytest.fixture(scope="module")
def live():
    try:
        return live_definitions()
    except httpx.TransportError as exc:
        pytest.skip(f"Energi Data Service unreachable: {exc}")


def test_every_column_we_read_still_exists(live):
    expected = {f"{d}.{c}" for d, cols in used_columns().items() for c in cols}
    assert expected - live.keys() == set()


def test_definitions_match_the_pin(live):
    pinned = json.loads(PINNED.read_text())
    changed = {
        k: {"pinned": pinned.get(k), "live": v}
        for k, v in live.items()
        if pinned.get(k) != v
    }
    assert not changed, json.dumps(changed, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    PINNED.parent.mkdir(exist_ok=True)
    PINNED.write_text(
        json.dumps(live_definitions(), indent=2, sort_keys=True, ensure_ascii=False)
        + "\n"
    )
