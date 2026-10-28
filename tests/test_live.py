from datetime import UTC, datetime, timedelta

from nordcast import live

P1 = datetime(2026, 10, 28, 12, 16, tzinfo=UTC)
P2 = P1 + timedelta(minutes=1)


def ip(t, sd, pulled):
    return {"TimeUTC": t, "PriceArea": "DK1", "SatisfiedDemand": sd, "DominatingDirection": 1,
            "ImbalancePriceEUR": None, "aFRRUpMW": 0.0, "aFRRDownMW": 0.0, "pulled_at_utc": pulled}  # fmt: skip


def test_each_pull_is_a_vintage_at_its_pull_time():
    rows = [ip("2026-10-28T11:45:00", -86.0, P1), ip("2026-10-28T11:45:00", -90.0, P2)]
    obs = [
        o
        for o in live.replay("ImbalancePrice", rows, None)
        if o["series_id"].endswith("satisfied_demand")
    ]
    assert [(o["value"], o["published_at"], o["vintage_quality"]) for o in obs] == [
        (-86.0, P1, "exact"),
        (-90.0, P2, "exact"),
    ]


def test_since_skips_pulls_already_loaded_and_dk2_is_ignored():
    rows = [
        ip("2026-10-28T11:45:00", -86.0, P1),
        {**ip("2026-10-28T11:45:00", 5.0, P2), "PriceArea": "DK2"},
    ]
    assert live.replay("ImbalancePrice", rows, P1) == []


def test_a_5min_isp_appears_only_once_complete():
    def p(minute, pulled):
        return {"Minutes5UTC": f"2026-10-28T12:{minute:02d}:00", "PriceArea": "DK1",
                "SolarPower": 30.0, "OnshoreWindPower": 1.0, "OffshoreWindPower": 2.0,
                "pulled_at_utc": pulled}  # fmt: skip

    rows = [p(0, P1), p(5, P1), p(10, P2)]
    obs = [
        o
        for o in live.replay("ElectricityProdex5MinRealtime", rows, None)
        if o["series_id"].endswith("solar_mw")
    ]
    assert [(o["value"], o["published_at"]) for o in obs] == [(30.0, P2)]
