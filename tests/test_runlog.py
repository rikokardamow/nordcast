from functools import partial

import psycopg
import pytest

from nordcast.runlog import logged


def last_run(url):
    with psycopg.connect(url) as c:
        return c.execute(
            "select job, outcome, detail from run_log order by run_id desc limit 1"
        ).fetchone()


def test_ok_nothing_due_and_failed_are_all_recorded(test_db_url):
    connect = partial(psycopg.connect, test_db_url)
    with logged(connect, "test-job"):
        pass
    assert last_run(test_db_url) == ("test-job", "ok", None)

    with logged(connect, "test-job") as run:
        run.nothing_due("no release due")
    assert last_run(test_db_url) == ("test-job", "nothing_due", "no release due")

    with pytest.raises(RuntimeError), logged(connect, "test-job"):
        raise RuntimeError("EIA down")
    assert last_run(test_db_url) == ("test-job", "failed", "RuntimeError: EIA down")
