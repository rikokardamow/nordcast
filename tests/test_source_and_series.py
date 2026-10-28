import psycopg
import pytest


def test_energinet_is_an_open_source(db):
    row = db.execute(
        "select licence_class from source where source_id = 'energinet'"
    ).fetchone()
    assert row == ("open",)


def test_every_energinet_and_esett_series_is_15_min(db):
    rows = dict(
        db.execute(
            "select series_id, frequency from series"
            " where source_id in ('energinet', 'esett')"
        ).fetchall()
    )
    assert rows["energinet.dk1.satisfied_demand"] == "15min"
    assert rows["energinet.dk1.dominating_direction"] == "15min"
    assert set(rows.values()) == {"15min"}


def test_every_source_module_series_is_in_the_table(db):
    from nordcast.sources import energinet, energinet_rt, esett

    known = {r[0] for r in db.execute("select series_id from series").fetchall()}
    wanted = set(energinet.SERIES) | set(esett.SERIES) | {energinet_rt.SERIES_ID}
    assert wanted <= known


def test_unknown_licence_class_is_rejected(db):
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(
            "insert into source (source_id, name, licence_class, licence, attribution)"
            " values ('x', 'X', 'free', 'n/a', 'n/a')"
        )


def test_series_needs_a_known_source(db):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        db.execute(
            "insert into series (series_id, source_id, code, name, unit, frequency)"
            " values ('x.y', 'nope', 'Y', 'Y', 'b', '5min')"
        )


def test_browser_api_cannot_read_the_tables(db):
    db.execute("set local role anon")
    assert db.execute("select count(*) from source").fetchone() == (0,)
    assert db.execute("select count(*) from series").fetchone() == (0,)
