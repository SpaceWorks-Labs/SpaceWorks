"""Dedicated transaction guard transport for bounded free-profile work.

J owns tick coordination and durable uncertain-attempt reconciliation. This helper
never claims a lease, reconnects, or permits takeover after loss on its own.
"""

from contextlib import contextmanager
from dataclasses import dataclass

from .connection import connect_database
from .session import SessionLost, lock_identity


@dataclass
class TransactionGuard:
    database: object
    pid: int
    key: tuple
    lost: bool = False

    def assert_valid(self):
        if self.lost or self.database.closed:
            raise SessionLost("The execution guard was lost; reconcile the attempt before retrying.")
        try:
            with self.database.cursor() as cursor:
                classid, objid, subid = lock_identity(self.key)
                cursor.execute(
                    "SELECT pg_backend_pid(), EXISTS (SELECT 1 FROM pg_locks WHERE "
                    "locktype='advisory' AND pid=pg_backend_pid() AND granted AND mode='ExclusiveLock' "
                    "AND classid=%s::oid AND objid=%s::oid AND objsubid=%s)",
                    [classid, objid, subid],
                )
                if cursor.fetchone() != (self.pid, True):
                    raise SessionLost("The execution guard no longer owns its transaction lock.")
        except Exception:
            self.lost = True
            raise SessionLost("The execution guard was lost; reconcile the attempt before retrying.") from None


@contextmanager
def transaction_guard(spec, key, *, budget_seconds=20):
    if not 1 <= budget_seconds <= 25:
        raise ValueError("Execution guard budget must be between 1 and 25 seconds.")
    key = tuple(key)
    if len(key) not in {1, 2}:
        raise ValueError("Invalid execution guard advisory key.")
    with connect_database(spec, autocommit=False) as database:
        guard = None
        try:
            with database.cursor() as cursor:
                cursor.execute("SELECT set_config('statement_timeout', %s, true)", [str(int(budget_seconds * 1000))])
                cursor.execute("SELECT set_config('idle_in_transaction_session_timeout', %s, true)", [str(int((budget_seconds + 5) * 1000))])
                placeholders = ", ".join(["%s"] * len(key))
                cursor.execute(f"SELECT pg_backend_pid(), pg_try_advisory_xact_lock({placeholders})", list(key))
                pid, acquired = cursor.fetchone()
                if acquired:
                    guard = TransactionGuard(database, pid, key)
            yield guard  # None means a competing chunk is active; skip immediately.
            if guard is not None:
                guard.assert_valid()
        finally:
            try:
                database.rollback()  # Guard connection never writes domain state.
            except Exception:
                if guard is not None:
                    guard.lost = True
                raise SessionLost("The execution guard connection was lost during cleanup.") from None
