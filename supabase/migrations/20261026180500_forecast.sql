-- Frozen calls. Written once before the release and never changed.
--   source_kind  model: our call. baseline: seasonal naive or last 4 weeks.
--                consensus: an outside poll, logged to compare against.
--   status       frozen, or auto_baseline when the model failed and a
--                baseline was frozen in its place (flagged, but on time).
create table forecast (
    forecast_id   bigint generated always as identity primary key,
    release_id    bigint not null references release (release_id),
    series_id     text not null references series (series_id),
    target_period date not null,
    source_kind   text not null check (source_kind in ('model', 'baseline', 'consensus')),
    method        text not null,
    status        text not null check (status in ('frozen', 'auto_baseline')),
    point         numeric not null,
    q10           numeric,
    q50           numeric,
    q90           numeric,
    data_cutoff   timestamptz not null,
    model_version text,
    flag_reason   text,
    frozen_at     timestamptz not null default now(),
    sha256        text not null,
    payload       jsonb not null,
    -- One call per method per release: a second freeze is refused.
    unique (release_id, source_kind, method)
);

create function forecast_before_release() returns trigger
language plpgsql as $$
declare
    due timestamptz;
begin
    -- The clock decides, not the caller.
    new.frozen_at := now();
    select scheduled_at into due from release where release_id = new.release_id;
    if new.frozen_at >= due then
        raise exception 'too late: release % was due at %', new.release_id, due;
    end if;
    return new;
end;
$$;

create trigger forecast_before_release
    before insert on forecast
    for each row execute function forecast_before_release();

create trigger forecast_frozen
    before update or delete on forecast
    for each row execute function refuse_change();

create trigger forecast_no_truncate
    before truncate on forecast
    for each statement execute function refuse_change();

alter table forecast enable row level security;
