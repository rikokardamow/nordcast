-- now() is when the transaction began, and the freeze job opens its
-- transaction before the models run, so a slow model could write after the
-- release and still pass. clock_timestamp() is the moment of the insert.
create or replace function forecast_before_release() returns trigger
language plpgsql as $$
declare
    due timestamptz;
begin
    -- The clock decides, not the caller.
    new.frozen_at := clock_timestamp();
    select scheduled_at into due from release where release_id = new.release_id;
    if new.frozen_at >= due then
        raise exception 'too late: release % was due at %', new.release_id, due;
    end if;
    return new;
end;
$$;
