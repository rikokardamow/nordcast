-- The value of a series for one period as it was known at a moment in time.
-- Every feature, band and baseline reads through this, so nothing published
-- after `asof` can leak into a forecast or a back-test.
create function value_asof(p_series text, p_period date, p_asof timestamptz)
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

revoke execute on function value_asof(text, date, timestamptz) from public, anon, authenticated;
