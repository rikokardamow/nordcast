"""Backups: dump the test database through Docker, restore it, push it.

Needs Docker and the local database, like the other database tests. Restores
go to their own scratch database, never the one the Sunday review uses.
"""

import contextlib
import json
import os
import subprocess
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from nordcast import backup

ADMIN = os.environ.get("NORDCAST_TEST_DATABASE_URL", backup.LOCAL_DB)
SCRATCH = "nordcast_restore_test"
NOW = datetime(2026, 10, 27, 20, 0, tzinfo=UTC)


@pytest.fixture
def docker_db(test_db_url):
    try:
        subprocess.run(
            ["docker", "exec", backup.container(), "true"], check=True, timeout=20
        )
    except (OSError, subprocess.SubprocessError):
        pytest.skip("database container not reachable through docker")
    return test_db_url


@pytest.fixture
def backup_repo(tmp_path):
    """A clone of an empty bare repo, standing in for the private GitHub repo."""
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    repo = tmp_path / "backups"
    subprocess.run(["git", "clone", "-q", str(remote), str(repo)], check=True)
    for key, value in [("user.name", "test"), ("user.email", "test@example.com")]:
        subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
    return repo, remote


def commits(path):
    out = subprocess.run(
        ["git", "--git-dir", str(path), "log", "--oneline", "--all"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return out.strip().splitlines()


def test_a_dump_restores_with_every_row(docker_db, tmp_path):
    with psycopg.connect(docker_db) as conn:
        manifest = {"counts": backup.counts(conn)}
    assert manifest["counts"]["release"] > 0
    backup.dump(tmp_path, docker_db)
    assert backup.restore_check(tmp_path, manifest, ADMIN, SCRATCH) == {}


def test_unchanged_data_dumps_byte_for_byte(docker_db, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    backup.dump(a, docker_db)
    backup.dump(b, docker_db)
    files = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
    assert files == sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
    assert all((a / f).read_bytes() == (b / f).read_bytes() for f in files)


def test_observations_split_by_series_and_month(db, docker_db, tmp_path):
    db.execute(
        "insert into observation (series_id, observed_for, value, published_at)"
        " values ('energinet.dk1.satisfied_demand', '2026-09-30 23:45+00', 1, now()),"
        " ('energinet.dk1.satisfied_demand', '2026-10-01 00:00+00', 2, now())"
    )
    db.commit()
    try:
        backup.dump(tmp_path, docker_db)
        base = tmp_path / "data" / "observation" / "energinet.dk1.satisfied_demand"
        assert sorted(p.name for p in base.iterdir()) == ["2026-09.csv", "2026-10.csv"]
        with psycopg.connect(docker_db) as conn:
            manifest = {"counts": backup.counts(conn)}
        assert backup.restore_check(tmp_path, manifest, ADMIN, SCRATCH) == {}
    finally:
        db.execute("set session_replication_role = replica")  # past insert-only
        db.execute("delete from observation")
        db.commit()


def test_restore_check_catches_missing_rows(docker_db, tmp_path):
    with psycopg.connect(docker_db) as conn:
        counts = backup.counts(conn)
    backup.dump(tmp_path, docker_db)
    short = {"counts": {**counts, "release": counts["release"] + 1}}
    assert backup.restore_check(tmp_path, short, ADMIN, SCRATCH) == {
        "release": (counts["release"] + 1, counts["release"])
    }


def test_backup_pushes_once_then_only_when_something_changes(
    docker_db, backup_repo, tmp_path
):
    repo, remote = backup_repo
    raw = tmp_path / "raw"
    (raw / "energinet").mkdir(parents=True)
    (raw / "energinet" / "pull-1.json").write_text("{}")
    with psycopg.connect(docker_db) as conn:
        assert backup.back_up(conn, repo, NOW, url=docker_db, raw=raw)
        assert len(commits(remote)) == 1  # pushed
        assert not backup.back_up(conn, repo, NOW, url=docker_db, raw=raw)
        assert len(commits(remote)) == 1  # nothing changed, no commit
        (raw / "energinet" / "pull-2.json").write_text("{}")
        assert backup.back_up(conn, repo, NOW, url=docker_db, raw=raw)
    assert len(commits(remote)) == 2
    assert (repo / "raw" / "energinet" / "pull-2.json").exists()
    manifest = json.loads((repo / "manifest.json").read_text())
    assert set(manifest["counts"]) == set(backup.TABLES)


def test_review_line_test_restores_the_latest_backup(docker_db, backup_repo, tmp_path):
    repo, _ = backup_repo
    with psycopg.connect(docker_db) as conn:
        backup.back_up(conn, repo, NOW, url=docker_db, raw=tmp_path / "none")
    now = datetime.now(UTC)
    line = backup.review_line(repo, now, ADMIN, SCRATCH)
    assert "test restore ok" in line and "STALE" not in line
    later = backup.review_line(repo, now + timedelta(days=9), ADMIN, SCRATCH)
    assert later.startswith("Backup: STALE")


def test_review_line_without_a_repo_says_so(tmp_path):
    assert "NOT SET UP" in backup.review_line(None, NOW)
    empty = tmp_path / "empty"
    subprocess.run(["git", "init", "-q", str(empty)], check=True)
    assert backup.review_line(empty, NOW).startswith("Backup: NONE")


def test_no_backup_repo_skips(monkeypatch, capsys):
    monkeypatch.delenv("NORDCAST_BACKUP_REPO", raising=False)
    assert backup.run("test") is False
    assert "NORDCAST_BACKUP_REPO not set" in capsys.readouterr().out


def test_a_failed_backup_never_raises(monkeypatch, backup_repo, test_db_url, capsys):
    repo, _ = backup_repo
    monkeypatch.setenv("NORDCAST_BACKUP_REPO", str(repo))
    monkeypatch.setenv("NORDCAST_BACKUP_DB_CONTAINER", "no-such-container")

    @contextlib.contextmanager
    def unlogged(conn_factory, job):  # keep run_log of the test database clean
        yield type("Run", (), {"detail": None})()

    monkeypatch.setattr(backup, "logged", unlogged)
    assert backup.run("test", url=test_db_url) is False
    assert "backup failed (test)" in capsys.readouterr().out
