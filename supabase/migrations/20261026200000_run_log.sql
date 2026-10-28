-- One row per job run, for the Sunday review and for spotting silent failures.
create table run_log (
    run_id      bigint generated always as identity primary key,
    job         text not null,
    started_at  timestamptz not null,
    finished_at timestamptz not null default now(),
    outcome     text not null check (outcome in ('ok', 'nothing_due', 'failed')),
    detail      text
);

create index run_log_recent on run_log (job, started_at desc);

alter table run_log enable row level security;
