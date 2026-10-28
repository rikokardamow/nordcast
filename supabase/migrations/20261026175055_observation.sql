-- Every value we ever saw, with three times:
--   observed_for  the period the value is about (week ending, day, month)
--   published_at  when the source made it public
--   ingested_at   when we pulled it
-- Rows are never changed. A revision is a new row with a later published_at.
create table observation (
    observation_id  bigint generated always as identity primary key,
    series_id       text not null references series (series_id),
    observed_for    date not null,
    value           numeric not null,
    published_at    timestamptz not null,
    ingested_at     timestamptz not null default now(),
    release_id      bigint references release (release_id),
    payload_hash    text not null,
    vintage_quality text not null default 'exact'
                    check (vintage_quality in ('exact', 'estimated')),
    -- The same value for the same period is only stored once, so re-pulling
    -- unchanged data adds nothing.
    unique (series_id, observed_for, payload_hash)
);

create index observation_asof on observation (series_id, observed_for, published_at);

create function observation_hash() returns trigger
language plpgsql as $$
begin
    new.payload_hash := encode(sha256(convert_to(
        new.series_id || '|' || new.observed_for || '|' || trim_scale(new.value),
        'UTF8')), 'hex');
    return new;
end;
$$;

create trigger observation_hash
    before insert on observation
    for each row execute function observation_hash();

create function refuse_change() returns trigger
language plpgsql as $$
begin
    raise exception '% is insert-only: % refused', tg_table_name, tg_op;
end;
$$;

create trigger observation_insert_only
    before update or delete on observation
    for each row execute function refuse_change();

create trigger observation_no_truncate
    before truncate on observation
    for each statement execute function refuse_change();

alter table observation enable row level security;
