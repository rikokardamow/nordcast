-- Challenger calls: other models frozen alongside the headline call, hashed
-- and scored the same way, so each builds a live record before it can be
-- promoted at a quarter boundary. Pages show only the 'model' row.
alter table forecast drop constraint forecast_source_kind_check;
alter table forecast add constraint forecast_source_kind_check
    check (source_kind in ('model', 'baseline', 'consensus', 'challenger'));
