"""Shared by the job entry points: the database URL and the archive path."""

import os
from pathlib import Path

LOCAL_DB = "postgresql://postgres:postgres@127.0.0.1:44332/postgres"
DB_URL = os.environ.get("NORDCAST_DATABASE_URL", LOCAL_DB)
ARCHIVE = Path(
    os.environ.get("NORDCAST_ARCHIVE_REPO", Path.home() / "nordcast-archive")
)
