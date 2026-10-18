"""Dedicated, lock-only transactions; no domain row lock spans remote I/O.

Namespace 734410 is reserved for cloud tick task exclusion (734411 for full
scheduler leadership). Stable SHA-256 signed-int32 keys never use Python hash().
A collision only serializes unrelated work; it cannot permit duplicate execution.
"""
from contextlib import contextmanager
import hashlib

import psycopg2
from django.db import connections

from .contracts import GuardLost

TICK_NAMESPACE = 734_410
LEADER_NAMESPACE = 734_411


def task_lock_key(key):
    return int.from_bytes(hashlib.sha256(key.encode("ascii")).digest()[:4], "big", signed=True)


def new_connection(timeout=5):
    # M's validated Django connection builder preserves provider TLS parameters.
    try:
        params = connections["default"].get_connection_params()
        params["connect_timeout"] = max(1, min(5, int(timeout)))
        return psycopg2.connect(**params)
    except Exception:
        raise GuardLost() from None


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
