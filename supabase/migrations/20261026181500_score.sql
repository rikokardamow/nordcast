-- One score per frozen forecast, against the first published figure.
-- Later revisions never change a score: actual is read as known at first print.
create table score (
    score_id        bigint generated always as identity primary key,
    forecast_id     bigint not null unique references forecast (forecast_id),
    actual          numeric not null,
    error           numeric not null,
    abs_error       numeric not null,
    first_print_at  timestamptz not null,
    outlier         boolean not null,
    status          text not null default 'scored'
                    check (status in ('scored', 'eia_delayed', 'revised_after')),
    scored_at       timestamptz not null default now()
);

create trigger score_insert_only
    before update or delete on score
    for each row execute function refuse_change();

create trigger score_no_truncate
    before truncate on score
    for each statement execute function refuse_change();

alter table score enable row level security;
