-- Series for the crude data page. Codes checked against
-- GET /v2/{route}/facet/series on 26 Oct 2026.
insert into series (series_id, source_id, code, name, unit, frequency) values
    ('eia.cushing', 'eia', 'PET.W_EPC0_SAX_YCUOK_MBBL.W',
     'Cushing, OK crude oil stocks excluding SPR', 'thousand barrels', 'weekly'),
    ('eia.wcrstus1', 'eia', 'PET.WCRSTUS1.W',
     'US crude oil stocks including SPR', 'thousand barrels', 'weekly'),
    ('eia.wcrfpus2', 'eia', 'PET.WCRFPUS2.W',
     'US field production of crude oil', 'thousand barrels per day', 'weekly'),
    ('eia.wcrimus2', 'eia', 'PET.WCRIMUS2.W',
     'US imports of crude oil', 'thousand barrels per day', 'weekly'),
    ('eia.wcrexus2', 'eia', 'PET.WCREXUS2.W',
     'US exports of crude oil', 'thousand barrels per day', 'weekly'),
    ('eia.wcrrius2', 'eia', 'PET.WCRRIUS2.W',
     'US refiner net input of crude oil', 'thousand barrels per day', 'weekly');

-- Newest vintage of each period, for charts. Open and derived series only.
create view web_latest as
select distinct on (series_id, observed_for)
       series_id, observed_for, value, published_at, attribution, licence_class
from web_observation
order by series_id, observed_for, published_at desc;

-- Release schedule. Public information.
create view web_release as
select release_kind, period_end, scheduled_at, basis, status,
       extract(isodow from scheduled_local) <> 3 as holiday_shift
from release;

-- One row per WPSR release: the frozen calls, the first print, the scores.
-- Everything the forecast card and scorecard need to work out their state.
create view web_card as
select r.period_end,
       r.scheduled_at,
       extract(isodow from r.scheduled_local) <> 3 as holiday_shift,
       m.point as model_point, m.q10, m.q90, m.model_version, m.sha256,
       m.status as model_status, m.flag_reason,
       sn.point as seasonal_point,
       l4.point as last4_point,
       (select avg(point) from forecast c
         where c.release_id = r.release_id and c.source_kind = 'consensus') as consensus_point,
       fp.first_print_at,
       ms.actual,
       ms.error as model_error, ms.abs_error as model_abs_error,
       ss.error as seasonal_error, ss.abs_error as seasonal_abs_error,
       ls.error as last4_error, ls.abs_error as last4_abs_error,
       ms.outlier
from release r
left join forecast m  on m.release_id = r.release_id and m.source_kind = 'model'
left join forecast sn on sn.release_id = r.release_id and sn.method = 'seasonal_naive'
left join forecast l4 on l4.release_id = r.release_id and l4.method = 'last_4_weeks'
left join score ms on ms.forecast_id = m.forecast_id
left join score ss on ss.forecast_id = sn.forecast_id
left join score ls on ls.forecast_id = l4.forecast_id
left join lateral (
    select min(published_at) as first_print_at from observation o
    where o.series_id = 'eia.wcestus1' and o.observed_for = r.period_end
) fp on true
where r.release_kind = 'wpsr';

revoke all on web_latest, web_release, web_card from anon, authenticated;
grant select on web_latest, web_release, web_card to anon, authenticated;
