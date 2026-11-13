"""Execution-lifetime exclusion on a dedicated PostgreSQL lock connection."""

from contextlib import contextmanager
import hashlib
import logging

import psycopg2
from django.db import connections

from .insertion_errors import MaterializationSuperseded


logger = logging.getLogger(__name__)
# Distinct from the source gate (734310) and PII (734201/734202) locks.
IMPORT_RUN_LOCK_NAMESPACE = 734_311


@contextmanager
def import_run_lock(job_id):
    lock = _ImportRunLock(job_id)
    try:
        lock.acquire()
        yield lock
    finally:
        lock.release()


class _ImportRunLock:
    def __init__(self, job_id):
        self.job_id = str(job_id)
        # Positive int32 keeps the pg_locks objid comparison unambiguous.
        self.key = int.from_bytes(
            hashlib.sha256(self.job_id.encode("ascii")).digest()[:4], "big"
        ) & 0x7fffffff
        self.acquired = False
        self.lock_connection = None
        self.backend_pid = None

    def acquire(self):
        self.lock_connection = _new_lock_connection()
        self.lock_connection.autocommit = False
        with self.lock_connection.cursor() as cursor:
            cursor.execute("SET LOCAL idle_in_transaction_session_timeout = 0")
            cursor.execute(
                "SELECT pg_try_advisory_xact_lock(%s, %s), pg_backend_pid()",
                [IMPORT_RUN_LOCK_NAMESPACE, self.key],
            )
            self.acquired, self.backend_pid = cursor.fetchone()
        if self.acquired:
            self.acquired = self.retained()

    def retained(self):
        if not self.acquired or self.lock_connection is None:
            return False
        try:
            with self.lock_connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT pg_backend_pid(), EXISTS (
                        SELECT 1 FROM pg_locks
                        WHERE locktype = 'advisory'
                          AND pid = pg_backend_pid()
                          AND classid = %s AND objid = %s
                          AND objsubid = 2 AND granted
                    )
                    """,
                    [IMPORT_RUN_LOCK_NAMESPACE, self.key],
                )
                backend_pid, held = cursor.fetchone()
            return backend_pid == self.backend_pid and bool(held)
        except psycopg2.Error:
            logger.exception(
                "tenant_import_run_lock_check_failed", extra={"job_id": self.job_id},
            )
            return False

    def require_retained(self):
        if not self.retained():
            raise MaterializationSuperseded("The import execution lock was lost.")

    def release(self):
        if self.lock_connection is None:
            return
        try:
            self.lock_connection.rollback()
        except Exception:
            logger.exception(
                "tenant_import_run_lock_rollback_failed", extra={"job_id": self.job_id},
            )
        finally:
            try:
                self.lock_connection.close()
            except Exception:
                logger.exception(
                    "tenant_import_run_lock_close_failed", extra={"job_id": self.job_id},
                )
            self.lock_connection = None
            self.acquired = False


def _new_lock_connection():
    # Never hold the application's connection in a transaction during archive I/O.
    from config.cloud_database import django_database_spec
    return psycopg2.connect(**django_database_spec().kwargs())
