"""The closed registry of cross-tenant capabilities: every path that may read across spaces.

A capability is never a general escape hatch. Each one names a path that is cross-tenant
by design; it is attached to exact routes (by URL name) or tasks (by Celery name) below,
and nowhere else except an explicit ``capability_context(name)`` in the code that owns
that path. Every use is audited as ``rls.capability_used`` (sampled: the first use per
capability and path in a process, then one in ``SAMPLE_EVERY``), with the path and the
actor kind only. ``tests/tenant_rls/test_cross_tenant_paths.py`` pins all three tables.
"""

import logging
from collections import Counter
from threading import Lock

from .context import Binding

logger = logging.getLogger(__name__)
SAMPLE_EVERY = 500

CAPABILITIES = {
    "public_directory": "The public list of makerspaces (every space's directory card).",
    "platform_console": "/control/, the superadmin control plane (superadmin always on, #110/#115).",
    "platform_reports": "Lane D platform-wide pages that compare and total across spaces (#115b).",
    "backup": "Deployment and per-space backup capture, including the PostgreSQL client tools.",
    "per_space_restore": "B2 per-space restore: re-links other spaces' rows that point into the space (#113).",
    "notification_fanout": "The notification outbox fan-out, which delivers for every space.",
    "tenant_migration": "Tenant migration export, import, pairing and source-gate work.",
    "collaboration": "Cross-space event and series collaboration: co-hosts read the host space's rows.",
}

# Exact URL names. Tenant-addressed routes not listed here are bound to their tenant.
ROUTE_CAPABILITIES = {
    "public-makerspaces": "public_directory",
    "admin-platform-dashboard": "platform_reports",
    "admin-platform-problems": "platform_reports",
    "admin-makerspace-usage": "platform_reports",
    "admin-deployment-backups": "backup",
    "admin-makerspace-backup-status": "backup",
    "admin-makerspace-backups": "backup",
    "admin-backup-download-url": "backup",
    "admin-makerspace-restores": "per_space_restore",
    "admin-space-restore": "per_space_restore",
    "admin-space-restore-confirm": "per_space_restore",
    "admin-space-restore-abort": "per_space_restore",
    "admin-restore-operations": "per_space_restore",
    "admin-restore-operation": "per_space_restore",
    "admin-restore-decision": "per_space_restore",
    **{name: "tenant_migration" for name in (
        "tenant-migration-deployment-identity", "tenant-migration-pairings", "tenant-migration-imports",
        "tenant-migration-import-upload-start", "tenant-migration-import-archive-chunk",
        "tenant-migration-import-archive-complete", "tenant-migration-import-detail",
        "tenant-migration-import-decisions", "tenant-migration-import-run",
        "tenant-migration-import-verification", "tenant-migration-target-activate",
        "tenant-migration-target-abort", "tenant-migration-disclosure-closure",
        "tenant-migration-disclosure-approvals", "tenant-migration-disclosure-revoke",
        "tenant-migration-exports", "tenant-migration-export-detail",
        "tenant-migration-export-download-url", "tenant-migration-source-quiesce",
        "tenant-migration-source-archive", "tenant-migration-source-recover",
        "admin-makerspace-selfhost-move-request",
    )},
    **{name: "collaboration" for name in (
        "admin-event-series-collaborators", "admin-event-series-collaboration-remove",
        "admin-event-series-collaboration-inbox", "admin-event-series-collaboration-respond",
        "admin-event-collaborators", "admin-event-collaboration-remove",
        "admin-event-collaboration-inbox", "admin-event-collaboration-respond",
        "member-collaborative-events", "member-collaborative-event-register",
    )},
}
# Path prefixes (the Django admin is mounted at /control/, never /admin/).
PATH_CAPABILITIES = (("/control/", "platform_console"),)

# Exact Celery task names. Tasks not listed run open unless they take a ``makerspace_id``.
TASK_CAPABILITIES = {
    "apps.integrations.notification_tasks.sweep_notification_outbox": "notification_fanout",
    "apps.backup.tasks.run_backup_archive_task": "backup",
    "apps.backup.tasks.scheduled_space_backups_task": "backup",
    "apps.backup.tasks.scheduled_deployment_backup_task": "backup",
    "apps.backup.tasks_space_restore.run_space_restore_preview_task": "per_space_restore",
    "apps.backup.tasks_space_restore.run_space_restore_apply_task": "per_space_restore",
    "apps.backup.tasks_space_restore.resume_space_restores_task": "per_space_restore",
    "apps.tenant_migration.tasks.run_migration_export_job_task": "tenant_migration",
    "apps.tenant_migration.tasks.run_import_job_task": "tenant_migration",
    "apps.tenant_migration.tasks.stage_import_job_task": "tenant_migration",
    "apps.tenant_migration.tasks.run_selfhost_move_export_task": "tenant_migration",
}

_counts = Counter()
_lock = Lock()


def require(name):
    if name not in CAPABILITIES:
        raise ValueError(f"Unknown RLS capability {name!r}; register it in tenant_rls.capabilities.")
    return name


def _sampled(name, label):
    with _lock:
        _counts[(name, label)] += 1
        count = _counts[(name, label)]
    return count == 1 or count % SAMPLE_EVERY == 0


def record_use(name, *, label, actor_kind):
    """Sampled ``rls.capability_used`` audit row; failure to audit never fails the path."""
    if not _sampled(name, label):
        return
    try:
        from django.db import transaction
        from apps.audit.services import record
        with transaction.atomic():
            record(None, "rls.capability_used", makerspace=None,
                   meta={"capability": name, "path": label[:200], "actor_kind": actor_kind})
    except Exception:
        logger.warning("tenant_rls_capability_audit_failed", extra={"capability": name, "path": label})


def capability_binding(name, *, label="", actor_kind="system"):
    require(name)
    record_use(name, label=label, actor_kind=actor_kind)
    return Binding(capability=name, label=label)


def reset_sampling():
    with _lock:
        _counts.clear()
