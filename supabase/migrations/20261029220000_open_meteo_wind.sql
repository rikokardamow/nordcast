-- DMI HARMONIE wind at six DK1 points, as forecast a day earlier, through
-- Open-Meteo (sources/open_meteo.py). Hourly; estimated vintages before the
-- live archive (29 Oct 2026), exact from it.
insert into source (source_id, name, licence_class, licence, attribution, url) values
    ('openmeteo', 'Open-Meteo (DMI HARMONIE model data)', 'open',
     'CC BY 4.0 data; free API for non-commercial use', 'Weather data by Open-Meteo.com',
     'https://open-meteo.com/');

insert into series (series_id, source_id, code, name, unit, frequency) values
    ('openmeteo.horns_rev.ws100_d1', 'openmeteo', 'previous_day1.wind_speed_100m.horns_rev',
     'Horns Rev (offshore): HARMONIE 100 m wind speed, run a day earlier', 'm/s', 'hourly'),
    ('openmeteo.horns_rev.wd100_d1', 'openmeteo', 'previous_day1.wind_direction_100m.horns_rev',
     'Horns Rev (offshore): HARMONIE 100 m wind direction, run a day earlier', 'degrees', 'hourly'),
    ('openmeteo.anholt.ws100_d1', 'openmeteo', 'previous_day1.wind_speed_100m.anholt',
     'Anholt (offshore): HARMONIE 100 m wind speed, run a day earlier', 'm/s', 'hourly'),
    ('openmeteo.anholt.wd100_d1', 'openmeteo', 'previous_day1.wind_direction_100m.anholt',
     'Anholt (offshore): HARMONIE 100 m wind direction, run a day earlier', 'degrees', 'hourly'),
    ('openmeteo.romo.ws100_d1', 'openmeteo', 'previous_day1.wind_speed_100m.romo',
     'Rømø: HARMONIE 100 m wind speed, run a day earlier', 'm/s', 'hourly'),
    ('openmeteo.romo.wd100_d1', 'openmeteo', 'previous_day1.wind_direction_100m.romo',
     'Rømø: HARMONIE 100 m wind direction, run a day earlier', 'degrees', 'hourly'),
    ('openmeteo.hvide_sande.ws100_d1', 'openmeteo', 'previous_day1.wind_speed_100m.hvide_sande',
     'Hvide Sande: HARMONIE 100 m wind speed, run a day earlier', 'm/s', 'hourly'),
    ('openmeteo.hvide_sande.wd100_d1', 'openmeteo', 'previous_day1.wind_direction_100m.hvide_sande',
     'Hvide Sande: HARMONIE 100 m wind direction, run a day earlier', 'degrees', 'hourly'),
    ('openmeteo.hanstholm.ws100_d1', 'openmeteo', 'previous_day1.wind_speed_100m.hanstholm',
     'Hanstholm: HARMONIE 100 m wind speed, run a day earlier', 'm/s', 'hourly'),
    ('openmeteo.hanstholm.wd100_d1', 'openmeteo', 'previous_day1.wind_direction_100m.hanstholm',
     'Hanstholm: HARMONIE 100 m wind direction, run a day earlier', 'degrees', 'hourly'),
    ('openmeteo.skagen.ws100_d1', 'openmeteo', 'previous_day1.wind_speed_100m.skagen',
     'Skagen: HARMONIE 100 m wind speed, run a day earlier', 'm/s', 'hourly'),
    ('openmeteo.skagen.wd100_d1', 'openmeteo', 'previous_day1.wind_direction_100m.skagen',
     'Skagen: HARMONIE 100 m wind direction, run a day earlier', 'degrees', 'hourly');
