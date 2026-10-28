"""Reads and writes against the point-in-time store."""

INSERT_OBSERVATION = (
    "insert into observation"
    " (series_id, observed_for, value, published_at, vintage_quality)"
    " values (%(series_id)s, %(observed_for)s, %(value)s, %(published_at)s,"
    " %(vintage_quality)s)"
    " on conflict (series_id, observed_for, payload_hash) do nothing"
)


def latest_values(conn, series_id):
    """{observed_for: value} using the newest vintage of each period."""
    rows = conn.execute(
        "select distinct on (observed_for) observed_for, value from observation"
        " where series_id = %s order by observed_for, published_at desc",
        (series_id,),
    ).fetchall()
    return dict(rows)


def release_times(conn, release_kind):
    rows = conn.execute(
        "select period_end, scheduled_at from release where release_kind = %s",
        (release_kind,),
    ).fetchall()
    return dict(rows)


def current_release(conn, release_kind, at):
    row = conn.execute(
        "select max(scheduled_at) from release"
        " where release_kind = %s and scheduled_at <= %s",
        (release_kind, at),
    ).fetchone()
    return row[0]


def insert_observations(conn, observations):
    """Insert rows, returning how many were new."""
    added = 0
    for obs in observations:
        added += conn.execute(INSERT_OBSERVATION, obs).rowcount
    return added


def value_asof(conn, series_id, period, asof):
    return conn.execute(
        "select value_asof(%s, %s, %s)", (series_id, period, asof)
    ).fetchone()[0]


def history_asof(conn, series_id, from_ts, to_ts, asof):
    """{observed_for: value} for every period in [from_ts, to_ts) as known at
    asof, in one query. Equal to calling value_asof for each period."""
    rows = conn.execute(
        "select * from history_asof(%s, %s, %s, %s)", (series_id, from_ts, to_ts, asof)
    ).fetchall()
    return dict(rows)


UPSERT_RELEASE = (
    "insert into release"
    " (source_id, release_kind, period_end, scheduled_local, scheduled_at, basis)"
    " values (%s, %s, %s, %s, %s, %s)"
    " on conflict (release_kind, period_end) do update set"
    " scheduled_local = excluded.scheduled_local,"
    " scheduled_at = excluded.scheduled_at, basis = excluded.basis,"
    " status = case when release.scheduled_local <> excluded.scheduled_local"
    " then 'shifted' else release.status end"
    " where release.scheduled_at > now()"
)


def load_releases(conn, source_id, release_kind, releases):
    """Insert new releases and move future ones whose time changed.
    Releases already due are never touched."""
    conn.cursor().executemany(
        UPSERT_RELEASE,
        [
            (
                source_id,
                release_kind,
                r.period_end,
                r.scheduled_local,
                r.scheduled_at,
                r.basis,
            )
            for r in releases
        ],
    )
