"""Post-purge cleanup keeps retrying all versions after bounded writes settle."""
from apps.operations.cloud_jobs import bounded
from datetime import timedelta
import logging
from django.db import connection, transaction
from django.db.models import Q
from uuid import uuid4
from django.utils import timezone
from apps.events.tasks_retention import require_retention_ready
from apps.makerspaces.models import Makerspace
from apps.makerspaces import limits
from apps.tenant_migration.gate_locks import shared_boundary
from .print_models import BadgePrintJob, BadgePrintCleanupReceipt
from . import print_storage

logger = logging.getLogger(__name__)


def capture_purge_locked(event_ids):
    if not connection.in_atomic_block:
        raise RuntimeError("Capture print custody in the authorized purge transaction.")
    now = timezone.now()
    for job in BadgePrintJob.objects.select_for_update().filter(event_id__in=event_ids).select_related("event").iterator(chunk_size=100):
        items = [(job.object_key, job.size_bytes, job.cleaned_at)]
        items += [(r.object_key, r.size_bytes, r.cleaned_at) for r in job.resources.iterator(chunk_size=100) if r.object_key]
        for key, size, cleaned_at in items:
            if not key:
                continue
            BadgePrintCleanupReceipt.objects.get_or_create(object_key=key, defaults={
                "makerspace_id_snapshot": job.event.makerspace_id, "event_id_snapshot": job.event_id,
                "size_bytes": size, "released": cleaned_at is not None,
                "not_before": now+timedelta(minutes=6), "next_attempt_at": now+timedelta(minutes=6)})


def cleanup_receipt(pk):
    original = BadgePrintCleanupReceipt.objects.get(pk=pk)
    with shared_boundary(original.makerspace_id_snapshot):
        require_retention_ready(original.makerspace_id_snapshot)
        with transaction.atomic():
            row = BadgePrintCleanupReceipt.objects.select_for_update().get(pk=pk)
            now = timezone.now()
            if row.not_before > now or row.next_attempt_at > now or row.lease_until and row.lease_until > now:
                return False
            token = uuid4()
            row.lease_token, row.lease_until = token, now+timedelta(minutes=5)
            row.save(update_fields=("lease_token", "lease_until"))
        # Storage is outside row locks. Exact locators are immutable and retries
        # remove late writes; the locked accounting mark makes release once-only.
        print_storage.delete(original.object_key)
        with transaction.atomic():
            tenant = Makerspace.objects.select_for_update().filter(pk=original.makerspace_id_snapshot).first()
            row = BadgePrintCleanupReceipt.objects.select_for_update().get(pk=pk)
            if row.lease_token != token or row.lease_until <= timezone.now():
                return False
            if not row.released:
                if tenant:
                    limits.free_storage(tenant, row.size_bytes)
                row.released = True
            row.cleaned_at = timezone.now()
            row.next_attempt_at = timezone.now()+timedelta(hours=6)
            row.attempts += 1
            row.lease_token = row.lease_until = None
            row.save(update_fields=("released", "cleaned_at", "next_attempt_at", "attempts", "lease_token", "lease_until"))
        return True


def sweep(limit=100):
    ids = list(BadgePrintCleanupReceipt.objects.filter(next_attempt_at__lte=timezone.now()).filter(Q(lease_until__isnull=True) | Q(lease_until__lte=timezone.now()))
        .order_by("next_attempt_at", "pk").values_list("pk", flat=True)[:min(max(limit, 1), 500)])
    for pk in bounded.items(ids):
        try:
            cleanup_receipt(pk)
        except Exception:
            receipt = BadgePrintCleanupReceipt.objects.get(pk=pk)
            with shared_boundary(receipt.makerspace_id_snapshot):
                require_retention_ready(receipt.makerspace_id_snapshot)
                with transaction.atomic():
                    BadgePrintCleanupReceipt.objects.filter(pk=pk).update(
                        next_attempt_at=timezone.now()+timedelta(hours=12))
            logger.warning("event_print_custody_cleanup_deferred", extra={"receipt_id": pk})
    return len(ids)
