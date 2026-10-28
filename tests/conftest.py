import os
from datetime import date
from pathlib import Path

import psycopg
import pytest
import vcr

from nordcast import store
from nordcast.calendar import RELEASE_KIND, isp_releases

# Local Supabase from `supabase start`. Override with NORDCAST_TEST_DATABASE_URL.
LOCAL_DB = "postgresql://postgres:postgres@127.0.0.1:44332/postgres"
TEST_DB = "nordcast_test"
MIGRATIONS = Path(__file__).parent.parent / "supabase" / "migrations"


@pytest.fixture(scope="session")
def test_db_url():
    """A fresh database built from the migrations, so tests never see or
    depend on whatever data is in the development database."""
    admin_url = os.environ.get("NORDCAST_TEST_DATABASE_URL", LOCAL_DB)
    try:
        admin = psycopg.connect(admin_url, connect_timeout=3, autocommit=True)
    except psycopg.OperationalError:
        pytest.skip("local database not running (supabase start)")
    with admin:
        admin.execute(f"drop database if exists {TEST_DB} with (force)")
        admin.execute(f"create database {TEST_DB}")
    url = admin_url.rsplit("/", 1)[0] + f"/{TEST_DB}"
    with psycopg.connect(url, autocommit=True) as conn:
        # Supabase's own defaults: the browser roles get every table in public,
        # so only row level security and the views stand in their way.
        conn.execute(
            "grant usage on schema public to anon, authenticated;"
            " alter default privileges in schema public"
            " grant all on tables to anon, authenticated;"
            " alter default privileges in schema public"
            " grant all on functions to anon, authenticated;"
        )
        for migration in sorted(MIGRATIONS.glob("*.sql")):
            conn.execute(migration.read_text())
        # Four days around the October 2026 clock change.
        releases = isp_releases(date(2026, 10, 24), date(2026, 10, 27))
        store.load_releases(conn, "energinet", RELEASE_KIND, releases)
    return url


@pytest.fixture
def db(test_db_url):
    conn = psycopg.connect(test_db_url)
    # Each test runs in a transaction that is rolled back, so nothing sticks.
    conn.autocommit = False
    yield conn
    conn.rollback()
    conn.close()


# Replays tests/cassettes. Records only when a cassette is missing.
recorder = vcr.VCR(
    cassette_library_dir="tests/cassettes",
    record_mode="once",
    decode_compressed_response=True,
)
