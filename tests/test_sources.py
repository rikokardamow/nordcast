from datetime import UTC, datetime, timedelta

import httpx
import pytest
from conftest import recorder

from nordcast import store
from nordcast.sources import energinet, energinet_rt, esett

ISP = datetime(2026, 10, 27, 11, 0, tzinfo=UTC)


def rows5(col, values, types=None):
    out = []
    for i, v in enumerate(values):
        t = (ISP + timedelta(minutes=5 * i)).strftime("%Y-%m-%dT%H:%M:%S")
        for ft in types or [None]:
            r = {"Minutes5UTC": t, "PriceArea": "DK1", col: v}
            if ft:
                r["ForecastType"] = ft
            out.append(r)
    return out


def test_five_minute_values_average_into_the_isp():
    spec = energinet.SERIES["energinet.dk1.solar_mw"]
    assert energinet.isp_values(spec, rows5("SolarPower", [10, 20, 30])) == {ISP: 20}


def test_an_isp_with_a_missing_piece_is_left_out():
    spec = energinet.SERIES["energinet.dk1.solar_mw"]
    assert energinet.isp_values(spec, rows5("SolarPower", [10, None, 30])) == {}
    assert energinet.isp_values(spec, rows5("SolarPower", [10, 20])) == {}


def test_a_forecast_series_reads_only_its_own_type():
    spec = energinet.SERIES["energinet.dk1.wind_onshore_fc_da_mw"]
    rows = rows5("ForecastDayAhead", [100, 100, 100], ["Onshore Wind"])
    rows += rows5("ForecastDayAhead", [900, 900, 900], ["Offshore Wind"])
    assert energinet.isp_values(spec, rows) == {ISP: 100}
    offshore_only = rows5("ForecastDayAhead", [900, 900, 900], ["Offshore Wind"])
    assert energinet.isp_values(spec, offshore_only) == {}


@pytest.mark.parametrize("series_id", sorted(energinet.SERIES))
def test_every_lag_respects_when_the_value_can_exist(series_id):
    published = energinet.NOMINAL_LAG[series_id](ISP)
    if "_fc_" in series_id:
        assert published < ISP  # a forecast is out before its ISP
    elif series_id.endswith("da_price_eur"):
        assert published <= ISP - timedelta(hours=10)
    else:
        assert published >= ISP + timedelta(minutes=15)  # an actual, after the ISP ends


def test_lags_are_no_earlier_than_the_measured_first_prints():
    # Archive, 28 Oct 2026: SatisfiedDemand first seen 6.5-10.3 min after the
    # ISP ended, prices up to ~20 min after that. Lags must err late.
    end = ISP + timedelta(minutes=15)
    assert energinet.NOMINAL_LAG["energinet.dk1.satisfied_demand"](
        ISP
    ) >= end + timedelta(minutes=10.3)
    assert energinet.NOMINAL_LAG["energinet.dk1.imbalance_price_eur"](
        ISP
    ) >= end + timedelta(minutes=30)


def test_day_before_lags_follow_copenhagen_across_the_clock_change():
    lag = energinet.NOMINAL_LAG["energinet.dk1.da_price_eur"]
    summer = datetime(2026, 10, 24, 10, 0, tzinfo=UTC)  # CEST
    winter = datetime(2026, 10, 27, 10, 0, tzinfo=UTC)  # CET
    assert lag(summer) == datetime(2026, 10, 23, 11, 0, tzinfo=UTC)
    assert lag(winter) == datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


def test_429_waits_and_retries():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429)
        return httpx.Response(200, json={"records": [{"x": 1}]})

    waits = []
    client = httpx.Client(transport=httpx.MockTransport(handler))
    rows = energinet.fetch(
        "ImbalancePrice", ISP, ISP + timedelta(hours=1), client, waits.append
    )
    assert rows == [{"x": 1}]
    assert waits == [60]
    assert calls[-1].url.params["timezone"] == "UTC"


def test_esett_placeholder_zeros_are_dropped():
    row = {"timestampUTC": "2026-10-27T11:00:00Z", "mainDirRegPowerPerMBA": 0.0}
    row |= dict.fromkeys(esett.PRICE_COLS, 0.0)
    assert esett.to_observations([row]) == []
    real = {**row, "imblSalesPrice": 53.6, "mainDirRegPowerPerMBA": -1.0}
    obs = esett.to_observations([real])
    assert {o["series_id"]: o["value"] for o in obs} == {
        "esett.dk1.imbalance_price_eur": 53.6,
        "esett.dk1.direction": -1.0,
    }


def test_mfrr_request_issues_are_exact_vintages():
    nested = [
        {"timeStamp": "2026-10-28T18:00:01+00:00", "mtuStart": "2026-10-28T18:15:00+00:00",
         "values": [{"area": "DK1", "value": -86}, {"area": "DK2", "value": 0}]},
    ]  # fmt: skip
    (obs,) = energinet_rt.to_observations(nested)
    assert obs["observed_for"] == datetime(2026, 10, 28, 18, 15, tzinfo=UTC)
    assert obs["published_at"] == datetime(2026, 10, 28, 18, 0, 1, tzinfo=UTC)
    assert obs["vintage_quality"] == "exact"


@recorder.use_cassette("energinet_imbalance_price_day.yaml")
def test_real_day_loads_once(db):
    start = datetime(2026, 10, 20, tzinfo=UTC)
    rows = energinet.fetch("ImbalancePrice", start, start + timedelta(days=1))
    obs = energinet.to_observations("ImbalancePrice", rows)
    assert (
        len([o for o in obs if o["series_id"] == "energinet.dk1.satisfied_demand"])
        == 96
    )
    first = store.insert_observations(db, obs)
    assert first == len(obs)
    assert store.insert_observations(db, obs) == 0


@recorder.use_cassette("esett_exp14_day.yaml")
def test_real_esett_day_matches_energinet_direction():
    start = datetime(2026, 10, 20, tzinfo=UTC)
    obs = esett.to_observations(esett.fetch(start, start + timedelta(days=1)))
    assert len([o for o in obs if o["series_id"] == "esett.dk1.direction"]) == 96
