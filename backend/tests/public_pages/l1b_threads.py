"""Independent DB workers with deterministic lock observation and bounded waits."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Event
from time import monotonic, sleep
from django.db import connection, connections


@contextmanager
def database_worker(operation):
    started, state = Event(), {}
    def run():
        connections.close_all()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET statement_timeout = '10s'")
                cursor.execute("SELECT pg_backend_pid()")
                state["pid"] = cursor.fetchone()[0]
            started.set()
            return operation()
        finally:
            connections.close_all()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(run)
        assert started.wait(5), "DB worker failed to start"
        yield future, state["pid"]


def wait_for_blocked(pid):
    until = monotonic() + 5
    while monotonic() < until:
        with connection.cursor() as cursor:
            cursor.execute("SELECT cardinality(pg_blocking_pids(%s))", [pid])
            if cursor.fetchone()[0]:
                return
        sleep(.01)
    raise AssertionError("Expected the concurrent writer to wait on the held lock")
