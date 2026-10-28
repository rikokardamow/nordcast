-- nordcast: the record at 15-min isp level instead of weekly.
-- Periods become instants (timestamptz), a call carries its horizon and a
-- direction, a score carries the direction and interval losses, and one
-- bulk read replaces period-by-period value_asof loops.

-- The crude pages' views pin the date columns; the site is behind a later
-- gate, so they go now and come back when it opens.
drop view web_card, web_release, web_latest, web_observation;

-- series and release: the new frequencies and the isp schedule.
alter table series drop constraint series_frequency_check;
alter table series add constraint series_frequency_check check (frequency in
    ('5min', '15min', 'hourly', 'daily', 'weekly', 'monthly', 'quarterly', 'annual'));

alter table release drop constraint release_basis_check;
alter table release add constraint release_basis_check
    check (basis in ('eia_schedule', 'rule', 'isp'));
alter table release alter column tz set default 'Europe/Copenhagen';
alter table release alter column period_end type timestamptz
    using period_end::timestamp at time zone 'UTC';

-- A Copenhagen wall-clock time is ambiguous for the repeated hour in
-- October, so a caller may give scheduled_at itself; it must then agree with
-- scheduled_local. Without it, the database converts as before.
create or replace function release_set_utc() returns trigger
language plpgsql as $$
begin
    if new.scheduled_at is null
       or (tg_op = 'UPDATE' and new.scheduled_at = old.scheduled_at) then
        new.scheduled_at := new.scheduled_local at time zone new.tz;
    elsif (new.scheduled_at at time zone new.tz) <> new.scheduled_local then
        raise exception 'scheduled_at % is not % in %',
            new.scheduled_at, new.scheduled_local, new.tz;
    end if;
    return new;
end;
$$;

-- observation: periods are instants. The hash keeps 20261028120100's rule
-- (skip a row that repeats the newest vintage; hash published_at so a return
-- to an old value is kept) and formats the period in UTC, so it doesn't
-- depend on the session's time zone.
alter table observation alter column observed_for type timestamptz
    using observed_for::timestamp at time zone 'UTC';

create or replace function observation_hash() returns trigger
language plpgsql as $$
begin
    if value_asof(new.series_id, new.observed_for, new.published_at) = new.value then
        return null;
    end if;
    new.payload_hash := encode(sha256(convert_to(
        new.series_id || '|'
        || to_char(new.observed_for at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
        || '|' || trim_scale(new.value)
        || '|' || extract(epoch from new.published_at),
        'UTF8')), 'hex');
    return new;
end;
$$;

drop function value_asof(text, date, timestamptz);
create function value_asof(p_series text, p_period timestamptz, p_asof timestamptz)
returns numeric
language sql stable as $$
    select value
    from observation
    where series_id = p_series
      and observed_for = p_period
      and published_at <= p_asof
    order by published_at desc, observation_id desc
    limit 1
$$;
revoke execute on function value_asof(text, timestamptz, timestamptz)
    from public, anon, authenticated;

-- Every period in [from_ts, to_ts) as known at asof, in one query: the same
-- answer as calling value_asof for each period, without a query per period.
create function history_asof(
    p_series text, p_from timestamptz, p_to timestamptz, p_asof timestamptz)
returns table (observed_for timestamptz, value numeric)
language sql stable as $$
    select distinct on (o.observed_for) o.observed_for, o.value
    from observation o
    where o.series_id = p_series
      and o.observed_for >= p_from and o.observed_for < p_to
      and o.published_at <= p_asof
    order by o.observed_for, o.published_at desc, o.observation_id desc
$$;
revoke execute on function history_asof(text, timestamptz, timestamptz, timestamptz)
    from public, anon, authenticated;

-- forecast: one row per method and horizon, with a volume call, a direction
-- call, or both. Probabilities sum to 1.
alter table forecast alter column target_period type timestamptz
    using target_period::timestamp at time zone 'UTC';
alter table forecast add column horizon_min int not null check (horizon_min > 0);
alter table forecast drop constraint forecast_release_id_source_kind_method_key;
alter table forecast add constraint forecast_one_call
    unique (release_id, source_kind, method, horizon_min);
alter table forecast alter column point drop not null;
alter table forecast
    add column direction text check (direction in ('up', 'down', 'none')),
    add column p_up numeric check (p_up between 0 and 1),
    add column p_down numeric check (p_down between 0 and 1),
    add column p_none numeric check (p_none between 0 and 1),
    add constraint forecast_has_a_call check (point is not null or direction is not null),
    add constraint forecast_probabilities check (
        (p_up is null and p_down is null and p_none is null)
        or abs(p_up + p_down + p_none - 1) < 0.0001);

-- score: the direction and the interval, beside the point error.
alter table score alter column error drop not null;
alter table score alter column abs_error drop not null;
alter table score
    add column direction_actual text check (direction_actual in ('up', 'down', 'none')),
    add column direction_hit boolean,
    add column brier numeric,
    add column pinball_q10 numeric,
    add column pinball_q50 numeric,
    add column pinball_q90 numeric,
    add column covered boolean;
alter table score drop constraint score_status_check;
alter table score add constraint score_status_check
    check (status in ('scored', 'print_missing', 'revised_after', 'eia_delayed'));

-- Public views again, on the new types. Open and derived sources only.
create view web_observation as
select o.series_id, s.name as series_name, s.unit, o.observed_for, o.value,
       o.published_at, o.vintage_quality, src.attribution, src.licence_class
from observation o
join series s using (series_id)
join source src using (source_id)
where src.licence_class in ('open', 'derived');

create view web_latest as
select distinct on (series_id, observed_for)
       series_id, observed_for, value, published_at, attribution, licence_class
from web_observation
order by series_id, observed_for, published_at desc;

create view web_release as
select release_kind, period_end, scheduled_at, basis, status from release;

revoke all on web_observation, web_latest, web_release from anon, authenticated;
grant select on web_observation, web_latest, web_release to anon, authenticated;

-- The source and the two target series (sign: + = up, checked 28 oct 2026,
-- notes/sources.md). Feature series come with the source modules.
insert into source (source_id, name, licence_class, licence, attribution, url) values
    ('energinet', 'Energinet, Energi Data Service', 'open',
     'Energi Data Service terms of use', 'Data: Energinet, Energi Data Service',
     'https://www.energidataservice.dk/');

insert into series (series_id, source_id, code, name, unit, frequency) values
    ('energinet.dk1.satisfied_demand', 'energinet', 'ImbalancePrice.SatisfiedDemand.DK1',
     'DK1 mFRR satisfied demand (+ up, - down)', 'MW', '15min'),
    ('energinet.dk1.dominating_direction', 'energinet', 'ImbalancePrice.DominatingDirection.DK1',
     'DK1 dominating direction (1 up, 0 none, -1 down)', 'direction', '15min');
