"""Back up the record to a private git repo, off this Mac.

The frozen calls are in this repo, but the rest of the record lives only in
the local database: observation vintages, consensus rows, scores, the run
log. EIA can't rebuild past vintages, so a lost disk would lose them for
good. Each backup writes a plain-SQL dump, a manifest of row counts and a
copy of data/raw/ into the clone at NORDCAST_BACKUP_REPO, then commits and pushes.

Git history is the retention: the tables are insert-only, so each dump
differs from the last by a few lines, and nothing is pruned.

run() is called by every job that writes the record. It never raises, so a
backup problem can't fail a freeze or a score; failures go to run_log as job
'backup', which the Sunday review lists.
"""

import json
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import psycopg

from nordcast.runlog import logged

LOCAL_DB = "postgresql://postgres:postgres@127.0.0.1:44332/postgres"
TABLES = ["source", "series", "release", "observation", "forecast", "score", "run_log"]
SCRATCH = "nordcast_restore_check"
# pg_dump 17.6+ writes a random \restrict key unless given one; a fixed key
# keeps unchanged data byte-identical, so an unchanged record makes no commit.
RESTRICT_KEY = "nordcastbackup"
DUMP = "nordcast.sql"
MANIFEST = "manifest.json"


def container():
    name = os.environ.get("NORDCAST_BACKUP_DB_CONTAINER")
    if name:
        return name
    config = Path("supabase/config.toml").read_text()
    project = re.search(r'^project_id\s*=\s*"([^"]+)"', config, re.MULTILINE).group(1)
    return f"supabase_db_{project}"


def dump(out_path, dbname="postgres", run=subprocess.run):
    """Schema and data of our tables, plus the migration history."""
    with open(out_path, "wb") as out:
        run(
            [
                "docker", "exec", container(), "pg_dump", "-U", "postgres",
                "-d", dbname, "--schema=public", "--schema=supabase_migrations",
                f"--restrict-key={RESTRICT_KEY}",
            ],
            stdout=out,
            check=True,
            timeout=300,
        )  # fmt: skip


def counts(conn):
    return {t: conn.execute(f"select count(*) from {t}").fetchone()[0] for t in TABLES}


def sync_raw(src, dest):
    """Copy data/raw/ across. Raw pulls are never edited, only added."""
    src = Path(src)
    if src.exists():
        shutil.copytree(src, dest, dirs_exist_ok=True)


def git(repo, *args, check=True, **kw):
    return subprocess.run(["git", "-C", str(repo), *args], check=check, **kw)


def commit_and_push(repo, now):
    """Commit whatever changed and push. Returns True if there was a commit."""
    git(repo, "add", "-A")
    staged = git(repo, "diff", "--cached", "--quiet", check=False).returncode
    if staged == 0:
        return False
    git(repo, "commit", "-q", "-m", f"Backup {now:%Y-%m-%d %H:%M} UTC")
    git(repo, "push", "-q")
    return True


def back_up(conn, repo, now, dbname="postgres", raw="data/raw"):
    repo = Path(repo)
    # Counts first: the dump can only hold as many rows or more.
    manifest = {"counts": counts(conn)}
    dump(repo / DUMP, dbname)
    (repo / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    sync_raw(raw, repo / "raw")
    return commit_and_push(repo, now)


def run(reason, url=None):
    """Back up if NORDCAST_BACKUP_REPO is set. Never raises."""
    repo = os.environ.get("NORDCAST_BACKUP_REPO")
    if not repo:
        print("backup skipped: NORDCAST_BACKUP_REPO not set")
        return False
    url = url or os.environ.get("NORDCAST_DATABASE_URL", LOCAL_DB)
    try:
        with logged(lambda: psycopg.connect(url), "backup") as log:
            with psycopg.connect(url) as conn:
                committed = back_up(conn, repo, datetime.now(UTC))
            log.detail = f"{reason}: {'pushed' if committed else 'no change'}"
            print(f"backup ({reason}): {'pushed' if committed else 'no change'}")
            return committed
    except Exception as exc:  # noqa: BLE001 - a backup must never fail the caller
        print(f"backup failed ({reason}): {type(exc).__name__}: {exc}")
        return False


def restore_check(dump_path, manifest, admin_url=LOCAL_DB, scratch=SCRATCH):
    """Load the dump into a scratch database and compare row counts with the
    manifest. Returns {table: (expected at least, found)} for every mismatch."""
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(f"drop database if exists {scratch} with (force)")
        admin.execute(f"create database {scratch}")
    scratch_url = psycopg.conninfo.make_conninfo(admin_url, dbname=scratch)
    try:
        # The dump creates public itself; a new database already has an empty one.
        with psycopg.connect(scratch_url, autocommit=True) as conn:
            conn.execute("drop schema public cascade")
        with open(dump_path, "rb") as fd:
            loaded = subprocess.run(
                [
                    # supabase_admin, the image's real superuser: the dump sets
                    # default privileges for it, which postgres may not do.
                    "docker", "exec", "-i", container(), "psql", "-U", "supabase_admin",
                    "-d", scratch, "-q", "-v", "ON_ERROR_STOP=1",
                ],
                stdin=fd,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,  # checked below, to report psql's own error line
            )  # fmt: skip
        if loaded.returncode != 0:
            errors = [ln for ln in loaded.stderr.splitlines() if "ERROR" in ln]
            raise RuntimeError(
                f"restore failed: {(errors or [loaded.stderr])[0][:300]}"
            )
        with psycopg.connect(scratch_url) as conn:
            found = counts(conn)
    finally:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(f"drop database if exists {scratch} with (force)")
    return {
        t: (n, found.get(t))
        for t, n in manifest["counts"].items()
        if found.get(t, -1) < n
    }


def last_backup(repo):
    """Time of the last backup commit, or None."""
    out = git(
        repo, "log", "-1", "--format=%cI", capture_output=True, text=True, check=False
    )
    return datetime.fromisoformat(out.stdout.strip()) if out.stdout.strip() else None


STALE_AFTER_DAYS = 8


def review_line(repo, now, admin_url=LOCAL_DB, scratch=SCRATCH):
    """The Sunday review's backup line: how old it is, and a test restore."""
    if not repo:
        return "Backup: NOT SET UP (NORDCAST_BACKUP_REPO is empty; see docs/SETUP.md)."
    repo = Path(repo)
    when = last_backup(repo)
    if when is None or not (repo / DUMP).exists():
        return f"Backup: NONE in {repo}."
    age = (now - when).total_seconds() / 86_400
    head = f"Backup: last pushed {when:%a %d %b %H:%M} UTC ({age:.1f} days ago)"
    if age > STALE_AFTER_DAYS:
        head = (
            f"Backup: STALE, last pushed {when:%a %d %b %H:%M} UTC ({age:.0f} days ago)"
        )
    try:
        manifest = json.loads((repo / MANIFEST).read_text())
        bad = restore_check(repo / DUMP, manifest, admin_url, scratch)
    except Exception as exc:  # noqa: BLE001 - report, don't crash the review
        return f"{head}; RESTORE FAILED: {type(exc).__name__}: {exc}"
    if bad:
        return f"{head}; RESTORE FAILED, short rows: {bad}"
    rows = sum(manifest["counts"].values())
    return f"{head}; test restore ok ({rows} rows)."
