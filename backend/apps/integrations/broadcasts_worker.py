"""One batch engine for concrete event and booking campaigns (200 accounts per task)."""

import logging

from celery import shared_task
from django.db import transaction
from django.db.models import IntegerField, Q
from django.db.models.functions import Cast, Coalesce
from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.audit.services import record
from apps.encryption.write_fence import assert_mapped_write_allowed
from apps.integrations.dispatch_outbox import dispatch_email
from apps.makerspaces.models import Makerspace
from apps.tenant_migration.gate_runtime import _boundary_shared_locks, assert_write_allowed, fanout_tenant_write
from .broadcasts_registry import ADAPTERS
from .broadcasts_delivery import ATTEMPTS_PER_RETRY, RETRY_START

logger = logging.getLogger(__name__)
BATCH_SIZE = 200


def enqueue(kind, pk):
    try:
        broadcast_batch.delay(kind, pk)
    except Exception as exc:
        # The durable queued/sending row is recoverable by resume_broadcasts.
        logger.error("broadcast_enqueue_failed", extra={"kind": kind, "campaign_id": pk, "error_class": type(exc).__name__})


@shared_task
def broadcast_batch(kind, pk):
    adapter = ADAPTERS.get(kind)
    if adapter is None:
        return
    candidate = adapter.campaign_model.objects.filter(pk=pk).first()
    if candidate is None:
        return
    with transaction.atomic():
        assert_write_allowed(candidate.makerspace_id)
        assert_mapped_write_allowed(candidate.makerspace_id)
        # Cancellation holds the tenant before the campaign. Outbox/audit FKs
        # also need the tenant, so taking the campaign first can deadlock.
        makerspace = Makerspace.objects.select_for_update().get(pk=candidate.makerspace_id)
        campaign = adapter.campaign_model.objects.select_for_update().get(pk=pk)
        campaign.makerspace = makerspace
        if campaign.status not in {"queued", "sending"} or campaign.recipients_complete:
            return
        try:
            adapter.authorize(campaign, campaign.created_by)
        except APIException:
            transition(adapter, campaign, "cancelled")
            return
        if campaign.status == "queued":
            transition(adapter, campaign, "sending")
        accounts = list(adapter.recipients(campaign).filter(pk__gt=campaign.recipient_cursor)
                        .order_by("pk").distinct()[:BATCH_SIZE])
        for account in accounts:
            if not adapter.eligible(campaign, account):
                continue
            delivery, created = adapter.delivery_model.objects.get_or_create(campaign=campaign, recipient=account)
            if not created:
                continue
            # Both inserts share this transaction. No crash can create an orphan send.
            log = dispatch_email(
                makerspace=campaign.makerspace, to_email=account.email, recipient_id=account.pk,
                subject="Broadcast", text_body="", feature=adapter.feature, stream=adapter.feature,
                event="broadcast", audience="requester", source_kind=kind, source_id=delivery.pk,
            )
            delivery.outbox = log
            delivery.status = log.status if log.status in {"skipped", "failed"} else "pending"
            delivery.save(update_fields=["outbox", "status", "updated_at"])
            record(None, f"{adapter.audit_prefix}.delivery_queued", makerspace=campaign.makerspace, target=delivery)
        if accounts:
            campaign.recipient_cursor = accounts[-1].pk
        campaign.recipients_complete = len(accounts) < BATCH_SIZE
        campaign.save(update_fields=["recipient_cursor", "recipients_complete", "updated_at"])
        record(None, f"{adapter.audit_prefix}.batch_queued", makerspace=campaign.makerspace,
               target=campaign, meta={"count": len(accounts)})
        if not campaign.recipients_complete:
            transaction.on_commit(lambda: enqueue(kind, pk))
    reconcile(kind, pk)


def transition(adapter, campaign, status):
    campaign.status = status
    if status in {"sent", "cancelled", "failed"}:
        campaign.completed_at = timezone.now()
    campaign.save(update_fields=["status", "completed_at", "updated_at"])
    record(None, f"{adapter.audit_prefix}.{status}", makerspace=campaign.makerspace, target=campaign)


def reconcile(kind, pk):
    adapter = ADAPTERS[kind]
    with transaction.atomic():
        candidate = adapter.campaign_model.objects.filter(pk=pk).first()
        if candidate is None:
            return
        # Reuse delivery/recovery's dedicated lock; standalone calls still gate
        # their application transaction before taking campaign row locks.
        if candidate.makerspace_id not in _boundary_shared_locks.get():
            assert_write_allowed(candidate.makerspace_id)
        assert_mapped_write_allowed(candidate.makerspace_id)
        makerspace = Makerspace.objects.select_for_update().get(pk=candidate.makerspace_id)
        campaign = adapter.campaign_model.objects.select_for_update().get(pk=pk)
        campaign.makerspace = makerspace
        if campaign.status != "sending" or not campaign.recipients_complete:
            return
        deliveries = adapter.delivery_model.objects.filter(campaign=campaign)
        if deliveries.filter(status="pending").exists():
            return
        transition(adapter, campaign, "failed" if deliveries.filter(status="failed").exists() else "sent")


def recover_for_tenants(work, *, operation, counts, callback):
    """Run (tenant ID, callback arguments) work items with isolated write boundaries."""
    for makerspace_id, args in work:
        try:
            with fanout_tenant_write(makerspace_id, operation=operation, counts=counts) as allowed:
                if not allowed:
                    continue
                callback(*args)
        except Exception as exc:
            # Match the reminder sweep: a fenced/broken tenant cannot starve others.
            counts["failed"] = counts.get("failed", 0) + 1
            logger.error("broadcast_recovery_failed", extra={
                "makerspace_id": makerspace_id, "operation": operation,
                "failure_type": type(exc).__name__,
            })


def recover_for_tenant(makerspace_id, *, operation, counts, callback, args):
    # Keep the per-row entry point: a fetched outbox snapshot must be revalidated
    # inside its tenant boundary, even if a manual retry commits before entry.
    recover_for_tenants(((makerspace_id, args),), operation=operation, counts=counts, callback=callback)


def recovery_rows(queryset, tenant_field):
    """Give every tenant its own budget, including when earlier tenants are frozen."""
    tenants = queryset.order_by(tenant_field).values_list(tenant_field, flat=True).distinct()
    for makerspace_id in tenants.iterator(chunk_size=BATCH_SIZE):
        yield from queryset.filter(**{tenant_field: makerspace_id}).order_by("pk")[:BATCH_SIZE]


@shared_task
def resume_broadcasts():
    from .dispatch_outbox import _enqueue
    counts = {"skipped": 0}
    # Missing metadata denotes the original four-attempt budget (legacy rows too).
    attempt_limit = Coalesce(Cast(f"outbox__source_metadata__{RETRY_START}", IntegerField()), 0) + ATTEMPTS_PER_RETRY
    for kind, adapter in ADAPTERS.items():
        # A crash after EmailLog.SENT committed but before the domain callback must
        # repair history without asking SMTP to accept the message a second time.
        from .delivery_sources import finished
        terminal = adapter.delivery_model.objects.filter(status="pending").filter(
            Q(outbox__status__in=["sent", "skipped"]) | Q(outbox__status="failed", outbox__attempts__gte=attempt_limit),
        ).select_related("outbox")
        for delivery in recovery_rows(terminal, "outbox__makerspace_id"):
            recover_for_tenant(delivery.outbox.makerspace_id, operation="broadcast_reconcile", counts=counts,
                               callback=finished, args=(delivery.outbox,))
        complete = adapter.campaign_model.objects.filter(status="sending", recipients_complete=True).values("pk", "makerspace_id")
        for row in recovery_rows(complete, "makerspace_id"):
            recover_for_tenant(row["makerspace_id"], operation="broadcast_completion", counts=counts,
                               callback=reconcile, args=(kind, row["pk"]))
        incomplete = adapter.campaign_model.objects.filter(status__in=["queued", "sending"],
                recipients_complete=False).values("pk", "makerspace_id")
        for row in recovery_rows(incomplete, "makerspace_id"):
            recover_for_tenant(row["makerspace_id"], operation="broadcast_resume", counts=counts,
                               callback=enqueue, args=(kind, row["pk"]))
        pending = adapter.delivery_model.objects.filter(
            campaign__status__in=["queued", "sending"], status="pending",
            outbox__status__in=["pending", "failed", "sending"], outbox__attempts__lt=attempt_limit,
        ).exclude(outbox__error__startswith="deferred:").values("outbox_id", "campaign__makerspace_id")
        for row in recovery_rows(pending, "campaign__makerspace_id"):
            recover_for_tenant(row["campaign__makerspace_id"], operation="broadcast_delivery_resume", counts=counts,
                               callback=_enqueue, args=(row["outbox_id"],))
