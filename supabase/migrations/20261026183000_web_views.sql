-- What the website may read. The browser uses the anon role, which can't
-- touch the base tables (row level security, no policies). These views run
-- as their owner and only pass through series whose source is open or
-- derived, so restricted data can't reach a page whatever the page asks for.
create view web_observation as
select o.series_id, s.name as series_name, s.unit, o.observed_for, o.value,
       o.published_at, o.vintage_quality, src.attribution, src.licence_class
from observation o
join series s using (series_id)
join source src using (source_id)
where src.licence_class in ('open', 'derived');

create view web_series as
select s.series_id, s.name, s.unit, s.frequency, src.attribution, src.licence_class
from series s
join source src using (source_id)
where src.licence_class in ('open', 'derived');

revoke all on web_observation, web_series from anon, authenticated;
grant select on web_observation, web_series to anon, authenticated;
