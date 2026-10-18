"""Brokerless consumers of existing durable domain queues; no generic queue.

I installs these adapters after preparing each domain's enqueue/lease delta.
Callbacks discover one bounded batch, retain domain idempotency and check fence()
before effects. A request only persists its existing job row in this profile.
"""
from dataclasses import asdict, dataclass

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .contracts import JobsUnavailable
from .outcomes import require_success


@dataclass(frozen=True)
class DurableWork:
    key: str
    model: str
    task: str
    app: str
    operation: str
    writer: str = "worker"


WORK = (
    DurableWork("bulk-import", "admin_api.BulkImportJob", "apps.admin_api.tasks.process_bulk_import_job",
                "admin_api", "bulk_import"),
    DurableWork("staff-export", "data_export.DataExportJob", "apps.data_export.tasks.run_data_export_task",
                "data_export", "data_export"),
    DurableWork("audit-verification", "audit.AuditVerificationRun", "apps.audit.tasks.run_audit_verification",
                "audit", "audit_verification"),
    DurableWork("tenant-export", "tenant_migration.TenantMigrationExportJob",
                "apps.tenant_migration.tasks.run_migration_export_job_task", "tenant_migration", "source_archive"),
    DurableWork("tenant-import-stage", "tenant_migration.TenantImportJob",
                "apps.tenant_migration.tasks.stage_import_job_task", "tenant_migration", "target_import"),
    DurableWork("tenant-import", "tenant_migration.TenantImportJob",
                "apps.tenant_migration.tasks.run_import_job_task", "tenant_migration", "target_import"),
)
_workers = {}


def install_worker(key, callback):
    if key not in {work.key for work in WORK} or not callable(callback):
        raise ImproperlyConfigured("Unknown persisted cloud work")
    if key in _workers and _workers[key] is not callback:
        raise ImproperlyConfigured("Duplicate persisted cloud worker")
    _workers[key] = callback


def run_persisted_work(*, fence, limit=25):
    if getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free":
        raise JobsUnavailable("free_profile_requires_tick_chunks")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Worker batch limit must be in 1..100")
    outcomes = {}
    for work in WORK:
        if work.app in settings.TOMBSTONED_APPS:
            continue
        fence()
        callback = _workers.get(work.key)
        if callback is None:
            outcomes[work.key] = "adapter_unavailable"
            continue
        try:
            require_success(callback(limit=limit, fence=fence))
            fence()
            outcomes[work.key] = "completed"
        except Exception:
            # Keep processing unrelated domain queues. A lost leader is fatal.
            fence()
            outcomes[work.key] = "failed"
    if any(value != "completed" for value in outcomes.values()):
        raise JobsUnavailable("persisted_work_incomplete")
    return outcomes


def worker_inventory():
    return [asdict(work) for work in WORK if work.app not in settings.TOMBSTONED_APPS]


def install_defaults():
    from . import work_adapters
    callbacks = (work_adapters.bulk_import, work_adapters.staff_export,
                 work_adapters.audit_verification, work_adapters.tenant_export,
                 work_adapters.tenant_import_stage, work_adapters.tenant_import)
    for work, callback in zip(WORK, callbacks):
        install_worker(work.key, callback)
