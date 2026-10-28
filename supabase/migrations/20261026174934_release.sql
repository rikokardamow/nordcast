-- One row per scheduled release. The time is kept as the source publishes it
-- (New York wall clock) and converted to UTC by the database, so clock
-- changes on either side of the Atlantic never need hard-coded offsets.
create table release (
    release_id      bigint generated always as identity primary key,
    source_id       text not null references source (source_id),
    release_kind    text not null,
    period_end      date not null,
    scheduled_local timestamp not null,
    tz              text not null default 'America/New_York',
    scheduled_at    timestamptz not null,
    basis           text not null check (basis in ('eia_schedule', 'rule')),
    status          text not null default 'scheduled'
                    check (status in ('scheduled', 'published', 'delayed', 'shifted')),
    created_at      timestamptz not null default now(),
    unique (release_kind, period_end)
);

create function release_set_utc() returns trigger
language plpgsql as $$
begin
    new.scheduled_at := new.scheduled_local at time zone new.tz;
    return new;
end;
$$;

create trigger release_set_utc
    before insert or update of scheduled_local, tz on release
    for each row execute function release_set_utc();

alter table release enable row level security;
