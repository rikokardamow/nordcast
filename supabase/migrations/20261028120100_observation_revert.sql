-- A revision back to an earlier value (A, then B, then A again) was dropped:
-- the hash covered only the value, so the third row matched the first. Now a
-- row is skipped only when it repeats the newest vintage before it, so
-- re-pulling unchanged data still adds nothing, and the hash covers
-- published_at so a return to an old value is a new row.
create or replace function observation_hash() returns trigger
language plpgsql as $$
begin
    if value_asof(new.series_id, new.observed_for, new.published_at) = new.value then
        return null;
    end if;
    new.payload_hash := encode(sha256(convert_to(
        new.series_id || '|' || new.observed_for || '|' || trim_scale(new.value)
        || '|' || extract(epoch from new.published_at),
        'UTF8')), 'hex');
    return new;
end;
$$;
