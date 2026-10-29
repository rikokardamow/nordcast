"""Energi Data Service: one fetch() and a mapper to ISP-level observations.

- No key. Rate limits are per dataset and answer HTTP 429; wait 60 s, retry.
- Times come back as naive strings; the *UTC columns are UTC.
- 5-minute rows are averaged to the 15-minute ISP only when all three are
  there; a missing piece drops the ISP rather than guessing it.
- History rows carry no publication time, so backfilled rows get
  published_at = a nominal lag (NOMINAL_LAG) and vintage_quality 'estimated'.
  Every lag errs late, so a backfilled value is never visible earlier than it
  really was. Checked against the archive's first prints on 28 Oct 2026.
"""

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

BASE_URL = "https://api.energidataservice.dk/dataset"
COPENHAGEN = ZoneInfo("Europe/Copenhagen")
ISP = timedelta(minutes=15)
WAIT_ON_429 = 60
RETRIES = 5


class EnerginetError(Exception):
    pass


def _end(isp):
    return isp + ISP


def _day_before_at(hour, minute=0):
    """hh:mm Copenhagen on the day before the ISP's Copenhagen day."""

    def lag(isp):
        day = isp.astimezone(COPENHAGEN).date() - timedelta(days=1)
        local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=COPENHAGEN)
        return local.astimezone(UTC)

    return lag


def _after_end(minutes):
    return lambda isp: _end(isp) + timedelta(minutes=minutes)


def _before_last_5min(minutes):
    """The ISP's last 5-minute value is due `minutes` before it starts."""
    return lambda isp: isp + timedelta(minutes=10) - timedelta(minutes=minutes)


@dataclass(frozen=True)
class Series:
    dataset: str
    time_col: str
    columns: tuple  # summed per row, e.g. onshore + offshore wind
    lag: object  # isp start (UTC) -> estimated published_at
    resolution_min: int = 15
    forecast_types: tuple = ()  # Forecasts_5Min rows to sum


# series_id -> how it's built. DK1 only. Lags from the archive's first prints
# (28 Oct 2026, padded) or the dataset's own description.
SERIES = {
    # measured first print 6-10 min after the ISP ends
    "energinet.dk1.satisfied_demand": Series(
        "ImbalancePrice", "TimeUTC", ("SatisfiedDemand",), _after_end(15)
    ),
    "energinet.dk1.dominating_direction": Series(
        "ImbalancePrice", "TimeUTC", ("DominatingDirection",), _after_end(15)
    ),
    # prices and aFRR fill in 5-20 min after the first print
    "energinet.dk1.imbalance_price_eur": Series(
        "ImbalancePrice", "TimeUTC", ("ImbalancePriceEUR",), _after_end(45)
    ),
    "energinet.dk1.afrr_up_mw": Series(
        "ImbalancePrice", "TimeUTC", ("aFRRUpMW",), _after_end(45)
    ),
    "energinet.dk1.afrr_down_mw": Series(
        "ImbalancePrice", "TimeUTC", ("aFRRDownMW",), _after_end(45)
    ),
    # not measured yet (archived from 28 Oct); an hour after the ISP until it is
    "energinet.dk1.mfrr_up_mw": Series(
        "MfrrEnergyActivationMarket", "TimeUTC", ("TotalmFRRUpMW",), _after_end(60)
    ),
    "energinet.dk1.mfrr_down_mw": Series(
        "MfrrEnergyActivationMarket", "TimeUTC", ("TotalmFRRDownMW",), _after_end(60)
    ),
    # Nord Pool day-ahead results, ~12:45-13:00 CET the day before
    "energinet.dk1.da_price_eur": Series(
        "DayAheadPrices", "TimeUTC", ("DayAheadPriceEUR",), _day_before_at(13, 0)
    ),
    # 5-min actuals post before each 5 minutes ends; the ISP is complete at its end
    # Onshore and offshore apart: the 5-min feed and the forecasts define
    # "offshore" differently (DK1 offshore runs ~900 MW above its forecast,
    # 27 Oct 2026), so each error is taken within its own type.
    "energinet.dk1.wind_onshore_mw": Series(
        "ElectricityProdex5MinRealtime",
        "Minutes5UTC",
        ("OnshoreWindPower",),
        _after_end(5),
        resolution_min=5,
    ),
    "energinet.dk1.wind_offshore_mw": Series(
        "ElectricityProdex5MinRealtime",
        "Minutes5UTC",
        ("OffshoreWindPower",),
        _after_end(5),
        resolution_min=5,
    ),
    "energinet.dk1.solar_mw": Series(
        "ElectricityProdex5MinRealtime",
        "Minutes5UTC",
        ("SolarPower",),
        _after_end(5),
        resolution_min=5,
    ),
    # Layer #32: demand - wind - solar, measured as thermal production + net
    # import (exchanges are + = import, tested). Exact by energy balance, so the
    # rooftop solar the feed misses drops out (docs/layers/residual-load).
    "energinet.dk1.residual_load_mw": Series(
        "ElectricityProdex5MinRealtime",
        "Minutes5UTC",
        (
            "ProductionLt100MW",
            "ProductionGe100MW",
            "ExchangeGreatBelt",
            "ExchangeGermany",
            "ExchangeNetherlands",
            "ExchangeGreatBritain",
            "ExchangeNorway",
            "ExchangeSweden",
        ),
        _after_end(5),
        resolution_min=5,
    ),
    # "updated close to 18:00 local Danish time" for the following day
    "energinet.dk1.wind_onshore_fc_da_mw": Series(
        "Forecasts_5Min",
        "Minutes5UTC",
        ("ForecastDayAhead",),
        _day_before_at(18, 30),
        resolution_min=5,
        forecast_types=("Onshore Wind",),
    ),
    "energinet.dk1.wind_offshore_fc_da_mw": Series(
        "Forecasts_5Min",
        "Minutes5UTC",
        ("ForecastDayAhead",),
        _day_before_at(18, 30),
        resolution_min=5,
        forecast_types=("Offshore Wind",),
    ),
    "energinet.dk1.solar_fc_da_mw": Series(
        "Forecasts_5Min",
        "Minutes5UTC",
        ("ForecastDayAhead",),
        _day_before_at(18, 30),
        resolution_min=5,
        forecast_types=("Solar",),
    ),
    # "might be updated until 1 minute before the forecast starts"
    "energinet.dk1.wind_onshore_fc_1h_mw": Series(
        "Forecasts_5Min",
        "Minutes5UTC",
        ("Forecast1Hour",),
        _before_last_5min(61),
        resolution_min=5,
        forecast_types=("Onshore Wind",),
    ),
    "energinet.dk1.wind_offshore_fc_1h_mw": Series(
        "Forecasts_5Min",
        "Minutes5UTC",
        ("Forecast1Hour",),
        _before_last_5min(61),
        resolution_min=5,
        forecast_types=("Offshore Wind",),
    ),
}
NOMINAL_LAG = {sid: s.lag for sid, s in SERIES.items()}
DATASETS = sorted({s.dataset for s in SERIES.values()})


def fetch(dataset, start, end, client=None, sleep=time.sleep):
    """Every DK1 row of `dataset` with start <= time < end (UTC datetimes)."""
    params = {
        "start": start.strftime("%Y-%m-%dT%H:%M"),
        "end": end.strftime("%Y-%m-%dT%H:%M"),
        "filter": '{"PriceArea":["DK1"]}',
        "timezone": "UTC",
        "limit": 0,
    }
    own = client is None
    client = client or httpx.Client(timeout=120)
    try:
        for attempt in range(RETRIES):
            try:
                r = client.get(f"{BASE_URL}/{dataset}", params=params)
            except httpx.TransportError:
                sleep(2**attempt)
                continue
            if r.status_code == 429:
                sleep(WAIT_ON_429)
                continue
            if r.status_code >= 500:
                sleep(2**attempt)
                continue
            r.raise_for_status()
            return r.json()["records"]
        raise EnerginetError(
            f"{dataset} {start:%F}..{end:%F}: gave up after {RETRIES} tries"
        )
    finally:
        if own:
            client.close()


def _utc(s):
    return datetime.fromisoformat(s[:19]).replace(tzinfo=UTC)


def _isp_start(t):
    return t - timedelta(minutes=t.minute % 15, seconds=t.second)


def isp_values(spec, records):
    """{isp start: value} for one series. ISPs with a missing piece are left out."""
    rows = [
        r
        for r in records
        if not spec.forecast_types or r["ForecastType"] in spec.forecast_types
    ]
    per_time = {}
    for r in rows:
        per_time.setdefault(_utc(r[spec.time_col]), []).append(r)
    need_rows = max(1, len(spec.forecast_types))
    point = {}
    for t, rs in per_time.items():
        vals = [r.get(c) for r in rs for c in spec.columns]
        if len(rs) == need_rows and all(v is not None for v in vals):
            point[t] = sum(vals)
    if spec.resolution_min == 15:
        return point
    per_isp = {}
    for t, v in point.items():
        per_isp.setdefault(_isp_start(t), []).append(v)
    n = 15 // spec.resolution_min
    return {isp: sum(vs) / n for isp, vs in per_isp.items() if len(vs) == n}


def to_observations(dataset, records):
    """Estimated-vintage observation rows for every series built from `dataset`."""
    out = []
    for series_id, spec in SERIES.items():
        if spec.dataset != dataset:
            continue
        for isp, value in isp_values(spec, records).items():
            out.append(
                {
                    "series_id": series_id,
                    "observed_for": isp,
                    "value": round(value, 4),
                    "published_at": spec.lag(isp),
                    "vintage_quality": "estimated",
                }
            )
    return out
