from celery import shared_task

from apps.backup.services import purge_expired_archives, run_archive, schedule_deployment_backup
from apps.backup.models import BackupArchive, BackupRun
from apps.backup.object_restore import cleanup_expired_rollback_objects
from apps.backup.reconciliation import reconcile_artifact_uploads


from apps.backup.tasks_space_restore import (  # noqa: E402,F401  (task registration)
    resume_space_restores_task,
    run_space_restore_apply_task,
    run_space_restore_preview_task,
)
from apps.backup.tasks_offsite import (  # noqa: E402,F401  (task registration)
    dispatch_offsite_push,
    push_offsite_backups_task,
    rehydrate_backup_archive_task,
)


@shared_task(bind=True, max_retries=0)
def run_backup_archive_task(self, archive_id):
    archive = run_archive(archive_id)
    available = bool(archive and archive.status == BackupArchive.Status.AVAILABLE)
    if available:
        from apps.backup.operator_notice import notify_archive_ready
        notify_archive_ready(archive)  # optional, off by default (#128 C-24); never raises
    if available and archive.scope == BackupArchive.Scope.DEPLOYMENT:
        # After the build released the deployment operation lock: the offsite push
        # must never hold it, and its failure must never fail this task.
        dispatch_offsite_push()
    return available


@shared_task(bind=True, max_retries=0)
def scheduled_deployment_backup_task(self):
    run = schedule_deployment_backup()
    if run is not None:
        from apps.backup.operator_notice import notify_archive_ready
        for archive in run.archives.filter(status=BackupArchive.Status.AVAILABLE):
            notify_archive_ready(archive)
        dispatch_offsite_push()
    return bool(run and run.status == BackupRun.Status.COMPLETE)


@shared_task(bind=True, max_retries=0)
def scheduled_space_backups_task(self):
    from apps.backup.space_backup_schedule import run_due_space_backups
    return run_due_space_backups()


@shared_task(bind=True, max_retries=0)
def purge_expired_backup_archives_task(self):
    return purge_expired_archives()


@shared_task(bind=True, max_retries=0)
def cleanup_expired_restore_rollbacks_task(self):
    return cleanup_expired_rollback_objects()


@shared_task(bind=True, max_retries=0)
def reconcile_backup_artifacts_task(self):
    return reconcile_artifact_uploads()


@shared_task(bind=True, max_retries=0)
def run_restore_drill_task(self):
    """Release 2 L11: one due restore drill per tick, isolated and throwaway (#128 C-22)."""
    from apps.backup.restore_drill import run_due_drill
    report = run_due_drill()
    return report.outcome if report is not None else None


@shared_task(bind=True, max_retries=0)
def reencrypt_archives_task(self):
    """Release 2 L11: one bounded batch of a requested re-encryption to the current keys."""
    from apps.backup.archive_reencrypt import run_requested_reencryption
    return run_requested_reencryption()
