"""Terminal-only rollback expiry under the deployment operation exclusion."""

from django.db import transaction
from django.utils import timezone

from .models import DeploymentRecoveryState, RestoreOperation, RestoreRollbackObject
from .operation_lock import deployment_operation_lock, OperationLockUnavailable

TERMINAL = (RestoreOperation.Stage.COMPLETED, RestoreOperation.Stage.RESTORED_QUARANTINED)


def cleanup_expired_rollback_objects(limit=100):
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Rollback cleanup limit is outside supported bounds.")
    acquired = False
    try:
        with deployment_operation_lock() as guard:
            acquired = True
            return _clean(limit, guard)
    except OperationLockUnavailable:
        if acquired:
            raise  # Losing an acquired guard is failure, never a quiet no-work pass.
        return 0


def _check(guard):
    if hasattr(guard, "assert_valid"):
        guard.assert_valid()


def _clean(limit, guard):
    from . import storage
    from .object_restore import _bucket
    from apps.object_storage import delete_all_versions
    from apps.makerspaces import limits

    cleaned = 0
    # Failure/abort is ambiguous: its retained copy/source is recovery material.
    ids = list(RestoreRollbackObject.objects.filter(
        expires_at__lte=timezone.now(), restore__stage__in=TERMINAL,
        restore__completed_at__isnull=False,
    ).order_by("pk").values_list("pk", flat=True)[:limit])
    for pk in ids:
        _check(guard)
        with transaction.atomic():
            row = RestoreRollbackObject.objects.select_for_update().filter(
                pk=pk, expires_at__lte=timezone.now()).first()
            if row is None:
                continue
            restore = RestoreOperation.objects.select_for_update().get(pk=row.restore_id)
            recovery = DeploymentRecoveryState.objects.select_for_update().filter(pk=1).first()
            if (restore.stage not in TERMINAL or restore.completed_at is None
                    or recovery is None or recovery.active_restore_id is not None
                    or recovery.mode != DeploymentRecoveryState.Mode.NORMAL
                    or RestoreOperation.objects.exclude(stage__in=(*TERMINAL, RestoreOperation.Stage.FAILED, RestoreOperation.Stage.ABORTED)).exists()):
                continue
            _check(guard)
            client = None
            try:
                client = storage.client()
                if row.copy_key:
                    delete_all_versions(client, bucket=_bucket(row.bucket_kind), key=row.copy_key)
                elif row.source_version_id:
                    client.delete_object(Bucket=_bucket(row.bucket_kind), Key=row.source_key, VersionId=row.source_version_id)
            except Exception:
                continue
            finally:
                if client is not None and hasattr(client, "close"):
                    client.close()
            _check(guard)
            if row.makerspace_id and row.size_bytes:
                limits.free_storage(row.makerspace, row.size_bytes)
            row.delete()
            cleaned += 1
    return cleaned
