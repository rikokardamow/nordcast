-- Wind actuals and forecasts by type. The 5-min feed and Forecasts_5Min define
-- "offshore" differently (DK1 offshore ~900 MW above its forecast, 27 Oct 2026),
-- so a combined error is biased; each type's error is taken within the type.
insert into series (series_id, source_id, code, name, unit, frequency) values
    ('energinet.dk1.wind_onshore_mw', 'energinet', 'ElectricityProdex5MinRealtime.OnshoreWindPower.DK1',
     'DK1 onshore wind production, ISP mean', 'MW', '15min'),
    ('energinet.dk1.wind_offshore_mw', 'energinet', 'ElectricityProdex5MinRealtime.OffshoreWindPower.DK1',
     'DK1 offshore wind production, ISP mean', 'MW', '15min'),
    ('energinet.dk1.wind_onshore_fc_da_mw', 'energinet', 'Forecasts_5Min.ForecastDayAhead.Onshore.DK1',
     'DK1 onshore wind day-ahead forecast, ISP mean', 'MW', '15min'),
    ('energinet.dk1.wind_offshore_fc_da_mw', 'energinet', 'Forecasts_5Min.ForecastDayAhead.Offshore.DK1',
     'DK1 offshore wind day-ahead forecast, ISP mean', 'MW', '15min'),
    ('energinet.dk1.wind_onshore_fc_1h_mw', 'energinet', 'Forecasts_5Min.Forecast1Hour.Onshore.DK1',
     'DK1 onshore wind 1-hour forecast, ISP mean', 'MW', '15min'),
    ('energinet.dk1.wind_offshore_fc_1h_mw', 'energinet', 'Forecasts_5Min.Forecast1Hour.Offshore.DK1',
     'DK1 offshore wind 1-hour forecast, ISP mean', 'MW', '15min');

-- The combined series stay (their rows are part of the record) but get no new rows.
update series set name = name || ' (superseded 28 Oct 2026 by the onshore/offshore series)'
where series_id in ('energinet.dk1.wind_mw', 'energinet.dk1.wind_fc_da_mw', 'energinet.dk1.wind_fc_1h_mw');
