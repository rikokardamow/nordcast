-- baseline_call: the week's call was a baseline, not a model. Either the
-- model failed and seasonal naive was frozen in its place (auto_baseline), or
-- the call came from model v0, which is seasonal naive with a band, used
-- until the model ladder starts. Such a call can't beat seasonal naive or
-- lose to it, so it's scored but never counted as a hit or a miss, and it's
-- left out of skill. One rule here, read by the site, the posts and the review.
--
-- Same view as before, with the new column added at the end.
create or replace view web_card as
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
       ms.outlier,
       coalesce(m.status = 'auto_baseline' or m.model_version like 'v0-%', false) as baseline_call
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
