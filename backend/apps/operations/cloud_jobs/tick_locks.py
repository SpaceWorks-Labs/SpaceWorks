"""Dedicated, lock-only transactions; no domain row lock spans remote I/O.

Free-profile tick exclusion. The namespaces, key derivation and dedicated
connection are shared with the full scheduler through ``advisory`` so a
full-profile process never imports this tick module.
"""
from contextlib import contextmanager

from .advisory import LEADER_NAMESPACE, TICK_NAMESPACE, new_connection, task_lock_key  # noqa: F401
from .contracts import GuardLost


class TaskGuard:
    def __init__(self, key, timeout):
        self.key = task_lock_key(key)
        self.timeout = max(1, int(timeout * 1000))
        self.connection = None
        self.pid = None
        self.acquired = False
        self.lost = False

    def acquire(self):
        try:
            self.connection = new_connection(self.timeout / 1000)
            self.connection.autocommit = False
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT set_config('statement_timeout', %s, true)", [str(self.timeout)])
                cursor.execute("SELECT set_config('idle_in_transaction_session_timeout', %s, true)",
                               [str(self.timeout + 1000)])
                cursor.execute("SELECT pg_try_advisory_xact_lock(%s, %s), pg_backend_pid()",
                               [TICK_NAMESPACE, self.key])
                self.acquired, self.pid = cursor.fetchone()
            return self.acquired
        except Exception:
            self.lost = True
            self.close()
            raise GuardLost() from None

    def check(self):
        if self.lost or not self.acquired or self.connection is None or self.connection.closed:
            self.lost = True
            raise GuardLost()
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""SELECT pg_backend_pid(), EXISTS (
                    SELECT 1 FROM pg_locks WHERE locktype='advisory'
                    AND pid=pg_backend_pid() AND classid=%s AND objid=%s
                    AND objsubid=2 AND granted)""", [TICK_NAMESPACE, self.key & 0xFFFFFFFF])
                pid, held = cursor.fetchone()
            if pid != self.pid or not held:
                raise GuardLost()
        except Exception:
            self.lost = True
            raise GuardLost() from None

    def close(self):
        if self.connection is not None:
            try:
                self.connection.close()  # rollback releases only this transaction's lock
            finally:
                self.connection = None


@contextmanager
def task_guard(key, timeout):
    guard = TaskGuard(key, timeout)
    try:
        yield guard if guard.acquire() else None
    finally:
        guard.close()
