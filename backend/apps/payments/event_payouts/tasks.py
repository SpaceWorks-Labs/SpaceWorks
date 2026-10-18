"""Bounded, fair core recovery; independent of rail/Events/reimbursement switches."""
import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .cleanup_models import FinanceSweepCursor

logger = logging.getLogger(__name__)


def normal_recovery():
    from apps.backup.models import DeploymentRecoveryState
    return DeploymentRecoveryState.objects.filter(pk=1, mode=DeploymentRecoveryState.Mode.NORMAL).exists()


def page(key, queryset, *, limit):
    """Persistent keyset cursor advances even over held/frozen/failed subjects."""
    with transaction.atomic():
        cursor, _ = FinanceSweepCursor.objects.get_or_create(key=key)
        cursor = FinanceSweepCursor.objects.select_for_update().get(pk=key)
        rows = queryset.filter(pk__gt=cursor.last_id) if cursor.last_id else queryset
        ids = list(rows.order_by("pk").values_list("pk", flat=True)[:limit])
        if not ids and cursor.last_id:
            ids = list(queryset.order_by("pk").values_list("pk", flat=True)[:limit])
        cursor.last_id = str(ids[-1]) if ids else ""
        cursor.save(update_fields=["last_id"])
        return ids


@shared_task
def sweep_retention_task(limit=100):
    if not normal_recovery():
        return {"recovery_blocked": True}
    from .attachment_models import FinanceAttachment
    from .obligation_models import EventPayoutObligation
    from .retention import expire_asset, purge_payees
    now, counts = timezone.now(), {"expired": 0, "payees_purged": 0, "retry": 0}
    limit = max(1, min(int(limit), 500))
    assets = FinanceAttachment.objects.exclude(state__in=("expired", "deleting", "deleted"))
    for asset_id in page("retention-assets", assets, limit=limit):
        try:
            counts["expired"] += bool(expire_asset(asset_id, now=now))
        except Exception:
            counts["retry"] += 1
            logger.warning("finance_retention_retry", extra={"asset_id": asset_id})
    from django.db.models import Q
    obligations = EventPayoutObligation.objects.filter(Q(state="open") | Q(payee_revisions__purge_due_at__lte=now)).distinct()
    for obligation_id in page("retention-payees", obligations, limit=limit):
        try:
            counts["payees_purged"] += purge_payees(obligation_id, now=now)
        except Exception:
            counts["retry"] += 1
            logger.warning("finance_payee_purge_retry", extra={"obligation_id": str(obligation_id)})
    return counts


@shared_task
def recover_finance_work_task(limit=100):
    if not normal_recovery():
        return {"recovery_blocked": True}
    from .attachment_models import FinanceAttachment
    from .attachment_workflow import process
    from .cleanup import due_ids, delete_one
    limit = max(1, min(int(limit), 500))
    counts = {"validated": 0, "deleted": 0, "retry": 0}
    for asset_id in page("recover-uploads", FinanceAttachment.objects.filter(state__in=("uploaded", "validating")), limit=limit):
        try:
            counts["validated"] += bool(process(asset_id))
        except Exception:
            counts["retry"] += 1
            logger.warning("finance_upload_retry", extra={"asset_id": asset_id})
    for cleanup_id in due_ids(now=timezone.now(), limit=limit):
        try:
            counts["deleted"] += bool(delete_one(cleanup_id))
        except Exception:
            counts["retry"] += 1
            logger.warning("finance_cleanup_retry", extra={"cleanup_id": str(cleanup_id)})
    return counts


def queue_retention(*, obligation_id=None, asset_id=None):
    """Broker loss is recoverable through the periodic retained sweep."""
    def enqueue():
        try:
            run_due_retention_task.delay(obligation_id=str(obligation_id) if obligation_id else None, asset_id=asset_id)
        except Exception:
            logger.warning("finance_retention_enqueue_retry", extra={"asset_id": asset_id,
                "obligation_id": str(obligation_id) if obligation_id else None})
    transaction.on_commit(enqueue, robust=True)


@shared_task
def run_due_retention_task(obligation_id=None, asset_id=None):
    if bool(obligation_id) == bool(asset_id):
        raise ValueError("One finance retention subject is required.")
    if not normal_recovery():
        return {"recovery_blocked": True}
    from .attachment_models import FinanceAttachment
    from .retention import expire_asset, purge_payees
    rows = FinanceAttachment.objects.filter(pk=asset_id) if asset_id else FinanceAttachment.objects.filter(obligation_id=obligation_id)
    counts = {"expired": 0, "payees_purged": 0, "retry": 0}
    for identifier in list(rows.exclude(state__in=("expired", "deleting", "deleted")).order_by("pk").values_list("pk", flat=True)[:100]):
        try:
            counts["expired"] += bool(expire_asset(identifier))
        except Exception:
            counts["retry"] += 1
    if obligation_id:
        counts["payees_purged"] = purge_payees(obligation_id)
    return counts
