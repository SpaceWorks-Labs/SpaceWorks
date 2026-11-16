"""Full managed scheduler leadership; host defaults keep their existing path.

Beat, loop and external dispatch must all enter leader() with the same key.
This session lock is deliberately separate from free tick transaction guards.
"""
from contextlib import contextmanager

from django.conf import settings

from .contracts import GuardLost, admit
from .advisory import LEADER_NAMESPACE, new_connection, task_lock_key


class FullLeader:
    def __init__(self, lane):
        self.connection = new_connection()
        self.connection.autocommit = True
        self.key = task_lock_key(lane)
        self.pid = None
        self.acquired = False
        self.lost = False

    def acquire(self):
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SET statement_timeout = '5000ms'")
                cursor.execute("SELECT pg_try_advisory_lock(%s, %s), pg_backend_pid()", [LEADER_NAMESPACE, self.key])
                self.acquired, self.pid = cursor.fetchone()
            return self.acquired
        except Exception:
            raise GuardLost() from None

    def check(self):
        if self.lost or self.connection.closed or not self.acquired:
            raise GuardLost()
        try:
            admit()
            with self.connection.cursor() as cursor:
                cursor.execute("""SELECT pg_backend_pid(), EXISTS (SELECT 1 FROM pg_locks
                    WHERE locktype='advisory' AND pid=pg_backend_pid() AND classid=%s
                    AND objid=%s AND objsubid=2 AND granted)""", [LEADER_NAMESPACE, self.key & 0xFFFFFFFF])
                pid, held = cursor.fetchone()
            if pid != self.pid or not held:
                raise GuardLost()
        except Exception:
            self.lost = True
            raise GuardLost() from None

    def close(self):
        self.connection.close()


@contextmanager
def leader(lane="scheduler"):
    if getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free":
        raise ValueError("Free profile requires the HTTP tick")
    if getattr(settings, "SPACEWORKS_DEPLOYMENT_MODE", "host") != "managed":
        yield None
        return
    admit()
    lock = FullLeader(lane)
    try:
        if not lock.acquire():
            raise GuardLost()
        lock.check()
        yield lock
    finally:
        lock.close()
