"""Application exclusion in managed mode, distinct from the host's root flock."""

from contextlib import contextmanager
import time

from config.cloud_database import connect_database, database_spec
from config.cloud_database.guards import TransactionGuard


# One documented, deployment-database-wide key for every archive/import contender.
OPERATION_KEY = (734_321, 1)


@contextmanager
def managed_operation_lock(*, blocking=False, timeout=30, environ=None):
    import os

    from apps.backup.operation_lock import OperationLockUnavailable
    from .admission import assert_binding, deployment_id

    source = os.environ if environ is None else environ
    spec = database_spec(source.get("DATABASE_URL", ""), managed=True, environ=source)
    try:
        with connect_database(spec) as database:
            assert_binding(database, deployment_id(source))
            deadline = time.monotonic() + (timeout if blocking else 0)
            with database.cursor() as cursor:
                while True:
                    cursor.execute("SELECT pg_backend_pid(), pg_try_advisory_lock(%s, %s)", list(OPERATION_KEY))
                    pid, acquired = cursor.fetchone()
                    if acquired:
                        break
                    if time.monotonic() >= deadline:
                        raise OperationLockUnavailable("Another deployment operation is already running.")
                    time.sleep(0.05)
            guard = TransactionGuard(database, pid, OPERATION_KEY)
            try:
                yield guard
                guard.assert_valid()
            finally:
                guard.assert_valid()
                with database.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_unlock(%s, %s)", list(OPERATION_KEY))
                    if cursor.fetchone()[0] is not True:
                        raise OperationLockUnavailable("The managed operation lock could not be released.")
    except OperationLockUnavailable:
        raise
    except Exception:
        raise OperationLockUnavailable("Managed operation exclusion was lost or unavailable.") from None
