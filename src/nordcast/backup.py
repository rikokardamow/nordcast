"""Back up the record to a private git repo, off this Mac.

The record lives only in the local database: observation vintages, frozen
calls, scores, the run log. Energinet doesn't keep first prints, so a lost
disk would lose them for good. Each backup writes the schema (pg_dump, in
pre-data and post-data sections) and every table as CSV in primary-key
order, observations split by series and month, the rest by month. A month
that's over never changes again, so each commit is small and no file nears
GitHub's 100 MB limit (a single dump of a million observations would).

Git history is the retention: the tables are insert-only, nothing is pruned.

run() never raises, so a backup problem can't fail a freeze or a score;
failures go to run_log as job 'backup'.
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
# table -> (primary key, time column the files are split on by month)
TABLES = {
    "source": ("source_id", None),
    "series": ("series_id", None),
    "release": ("release_id", "period_end"),
    "observation": ("observation_id", "observed_for"),
    "forecast": ("forecast_id", "target_period"),
    "score": ("score_id", "first_print_at"),
    "run_log": ("run_id", "started_at"),
}
SCRATCH = "nordcast_restore_check"
# pg_dump 17.6+ writes a random \restrict key unless given one; a fixed key
# keeps unchanged schema byte-identical, so an unchanged record makes no commit.
RESTRICT_KEY = "nordcastbackup"
DUMP = "schema.sql"
MIGRATIONS = "migrations.sql"
POST = "post.sql"
DATA = "data"
MANIFEST = "manifest.json"


def container():
    name = os.environ.get("NORDCAST_BACKUP_DB_CONTAINER")
    if name:
        return name
    config = Path("supabase/config.toml").read_text()
    project = re.search(r'^project_id\s*=\s*"([^"]+)"', config, re.MULTILINE).group(1)
    return f"supabase_db_{project}"


def _pg_dump(dbname, *args):
    return subprocess.run(
        ["docker", "exec", container(), "pg_dump", "-U", "postgres", "-d", dbname,
         f"--restrict-key={RESTRICT_KEY}", *args],
        capture_output=True, check=True, timeout=300,
    ).stdout  # fmt: skip


def _parts(conn, table):
    """[(relative csv path, where clause, params)] for one table."""
    _, col = TABLES[table]
    if col is None:
        return [(f"{table}.csv", "true", ())]
    month = f"to_char({col} at time zone 'UTC', 'YYYY-MM')"
    if table == "observation":
        rows = conn.execute(
            f"select distinct series_id, {month} from observation order by 1, 2"
        ).fetchall()
        return [
            (f"observation/{sid}/{m}.csv", f"series_id = %s and {month} = %s", (sid, m))
            for sid, m in rows
        ]
    rows = conn.execute(f"select distinct {month} from {table} order by 1").fetchall()
    return [(f"{table}/{m}.csv", f"{month} = %s", (m,)) for (m,) in rows]


def dump(out_dir, url):
    """Schema, migration history and every table as CSV, into out_dir."""
    out_dir = Path(out_dir)
    dbname = psycopg.conninfo.conninfo_to_dict(url)["dbname"]
    schemas = ("--schema=public", "--schema=supabase_migrations")
    (out_dir / DUMP).write_bytes(_pg_dump(dbname, *schemas, "--section=pre-data"))
    (out_dir / POST).write_bytes(_pg_dump(dbname, *schemas, "--section=post-data"))
    shutil.rmtree(out_dir / DATA, ignore_errors=True)
    with psycopg.connect(url) as conn:
        # supabase's migration history; a database built by the tests has none
        has_history = conn.execute(
            "select to_regnamespace('supabase_migrations') is not null"
        ).fetchone()[0]
        (out_dir / MIGRATIONS).write_bytes(
            _pg_dump(dbname, "--schema=supabase_migrations", "--data-only")
            if has_history
            else b""
        )
        for table, (pk, _) in TABLES.items():
            for rel, where, params in _parts(conn, table):
                path = out_dir / DATA / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                query = (
                    f"copy (select * from {table} where {where} order by {pk})"
                    " to stdout with (format csv, header)"
                )
                with open(path, "wb") as out, conn.cursor().copy(query, params) as copy:
                    out.writelines(copy)


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


def back_up(conn, repo, now, url=LOCAL_DB, raw="data/raw"):
    repo = Path(repo)
    # Counts first: the dump can only hold as many rows or more.
    manifest = {"counts": counts(conn)}
    dump(repo, url)
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
                committed = back_up(conn, repo, datetime.now(UTC), url)
            log.detail = f"{reason}: {'pushed' if committed else 'no change'}"
            print(f"backup ({reason}): {'pushed' if committed else 'no change'}")
            return committed
    except Exception as exc:  # noqa: BLE001 - a backup must never fail the caller
        print(f"backup failed ({reason}): {type(exc).__name__}: {exc}")
        return False


def _psql(dbname, sql_path):
    with open(sql_path, "rb") as fd:
        loaded = subprocess.run(
            [
                # supabase_admin, the image's real superuser: the dump sets
                # default privileges for it, which postgres may not do.
                "docker", "exec", "-i", container(), "psql", "-U", "supabase_admin",
                "-d", dbname, "-q", "-v", "ON_ERROR_STOP=1",
            ],
            stdin=fd, capture_output=True, text=True, timeout=300,
            check=False,  # checked below, to report psql's own error line
        )  # fmt: skip
    if loaded.returncode != 0:
        errors = [ln for ln in loaded.stderr.splitlines() if "ERROR" in ln]
        raise RuntimeError(f"restore failed: {(errors or [loaded.stderr])[0][:300]}")


def restore(backup_dir, url):
    """Load a backup into the empty database at url: schema, data, then the
    triggers and constraints, so loading doesn't re-run the insert triggers."""
    backup_dir = Path(backup_dir)
    dbname = psycopg.conninfo.conninfo_to_dict(url)["dbname"]
    # The dump creates public itself; a new database already has an empty one.
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("drop schema public cascade")
    _psql(dbname, backup_dir / DUMP)
    _psql(dbname, backup_dir / MIGRATIONS)
    with psycopg.connect(url) as conn:
        for table, (pk, _) in TABLES.items():
            files = sorted((backup_dir / DATA).glob(f"{table}.csv")) + sorted(
                (backup_dir / DATA / table).rglob("*.csv")
            )
            for path in files:
                with conn.cursor().copy(
                    f"copy {table} from stdin with (format csv, header)"
                ) as copy:
                    copy.write(path.read_bytes())
            seq = conn.execute(
                "select pg_get_serial_sequence(%s, %s)", (table, pk)
            ).fetchone()[0]
            if seq:
                conn.execute(
                    f"select setval(%s, coalesce((select max({pk}) from {table}), 0) + 1, false)",
                    (seq,),
                )
    _psql(dbname, backup_dir / POST)


def restore_check(backup_dir, manifest, admin_url=LOCAL_DB, scratch=SCRATCH):
    """Load the backup into a scratch database and compare row counts with the
    manifest. Returns {table: (expected at least, found)} for every mismatch."""
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(f"drop database if exists {scratch} with (force)")
        admin.execute(f"create database {scratch}")
    scratch_url = psycopg.conninfo.make_conninfo(admin_url, dbname=scratch)
    try:
        restore(backup_dir, scratch_url)
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
        bad = restore_check(repo, manifest, admin_url, scratch)
    except Exception as exc:  # noqa: BLE001 - report, don't crash the review
        return f"{head}; RESTORE FAILED: {type(exc).__name__}: {exc}"
    if bad:
        return f"{head}; RESTORE FAILED, short rows: {bad}"
    rows = sum(manifest["counts"].values())
    return f"{head}; test restore ok ({rows} rows)."
