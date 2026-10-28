"""Record each job run in run_log, whatever happens inside it."""

from contextlib import contextmanager
from datetime import UTC, datetime


class Run:
    def __init__(self):
        self.outcome = "ok"
        self.detail = None

    def nothing_due(self, detail=None):
        self.outcome, self.detail = "nothing_due", detail


@contextmanager
def logged(conn_factory, job):
    """Usage: with logged(lambda: psycopg.connect(url), "freeze") as run: ...

    Writes on its own connection, so a failed job's rollback can't erase
    the record that it failed.
    """
    run, started = Run(), datetime.now(UTC)
    try:
        yield run
    except Exception as exc:
        run.outcome, run.detail = "failed", f"{type(exc).__name__}: {exc}"[:500]
        raise
    finally:
        with conn_factory() as conn:
            conn.execute(
                "insert into run_log (job, started_at, outcome, detail)"
                " values (%s, %s, %s, %s)",
                (job, started, run.outcome, run.detail),
            )
