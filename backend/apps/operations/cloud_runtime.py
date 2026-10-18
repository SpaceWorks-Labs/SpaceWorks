"""Uncached managed admission and a process-generation fence shared by adapters."""
from contextlib import contextmanager
from contextvars import ContextVar
import os
import sys

from django.conf import settings
from django.db import connection

_writer = ContextVar("cloud_writer", default=None)


def managed():
    return getattr(settings, "SPACEWORKS_DEPLOYMENT_MODE", "host") == "managed"


def admit(*, refresh=False):
    if not managed():
        from apps.backup.managed.mode_binding import assert_mode_binding
        with connection.cursor() as cursor:
            assert_mode_binding(cursor, "host")
        return
    from apps.backup.managed.admission import ManagedAdmissionError, assert_managed_admission
    source = dict(os.environ)
    if (source.get("SPACEWORKS_FINITE_MAINTENANCE_JOB") == "1"
            and len(sys.argv) > 1 and sys.argv[1] in {"export_tenant_migration_archive", "export_portable_tenant_dump"}):
        for name in ("DATABASE_MAINTENANCE_URL", "SPACEWORKS_MAINTENANCE_DATABASE_URL", "CLOUD_SCRATCH_DATABASES_FILE"):
            source.pop(name, None)
    assert_managed_admission(source)
    boundary = _writer.get()
    expected = str(boundary.row.generation) if boundary else os.environ.get("SPACEWORKS_ADMITTED_GENERATION", "")
    with connection.cursor() as cursor:
        cursor.execute("SELECT generation, paused_by FROM backup_managedcapturestate WHERE id=1")
        row = cursor.fetchone()
    from apps.backup.managed.capture import admitted_capture
    if admitted_capture(row):
        return
    if refresh and row is not None and row[1] is None:
        # Only a NEW boundary can acknowledge the resumed generation. Work already
        # in progress retains its row generation and cannot acquire this proof.
        os.environ["SPACEWORKS_ADMITTED_GENERATION"] = str(row[0])
        expected = str(row[0])
    if row is None or str(row[0]) != expected or row[1] is not None:
        raise ManagedAdmissionError("This process generation is not admitted.")


def check():
    admit()
    boundary = _writer.get()
    if boundary is not None:
        boundary.assert_valid()


@contextmanager
def writer(category):
    if managed():
        from apps.backup.managed.capture import active_capture
        if active_capture():
            yield check
            return
    if not managed() or _writer.get() is not None:
        yield check
        return
    admit(refresh=True)
    from apps.backup.managed.writers import writer_boundary
    with writer_boundary(category) as boundary:
        token = _writer.set(boundary)
        try:
            check()
            yield check
            check()
        finally:
            _writer.reset(token)


def install():
    # Registration is query-free. The callback refuses without a launch generation.
    from .cloud_jobs.contracts import install_admission
    install_admission(check)
    from .cloud_jobs import adapters, work
    adapters.install()
    work.install_defaults()
    from .cloud_jobs.contracts import install_chunk
    from .storage_qualification import refresh_chunk
    install_chunk("cloud-storage-qualification", refresh_chunk)
    from apps.backup.managed.staging import cleanup_chunk
    install_chunk("cloud-private-staging-cleanup", cleanup_chunk)


def assert_scheduler_adapters_ready():
    if not managed() or settings.SPACEWORKS_DEPLOYMENT_PROFILE != "free":
        return
    from .cloud_jobs.catalog import periodic_catalog
    from .cloud_jobs.contracts import chunk_for
    from apps.backup.managed.admission import ManagedAdmissionError
    missing = [task.key for task in periodic_catalog()
               if task.free_policy != "disabled_in_free_profile" and chunk_for(task.key) is None]
    if missing:
        raise ManagedAdmissionError("Required bounded scheduler adapters are unavailable.")
