def test_every_table_has_row_level_security(db):
    # Supabase lets the browser role reach every table in public. Row level
    # security is what stops it, so a new table without it would leak.
    missing = db.execute(
        "select relname from pg_class c join pg_namespace n on n.oid = c.relnamespace"
        " where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity"
    ).fetchall()
    assert missing == []
