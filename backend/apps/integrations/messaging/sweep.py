"""Bounded recovery and retention, independent of the optional inbox module."""
import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.audit.services import record
from apps.integrations.models import MessagingDelivery, MessagingRecipientCorrelation, MessagingWebhookEvent
from apps.tenant_migration.gate_runtime import fanout_tenant_write, tenant_write
from .dispatch import schedule_delivery
from .locks import lock_whatsapp_sender
from .outcomes import observe, save_outcome
from .senders import wipe_retired_credentials
from .webhook_processing import process_event
from .worker import due_filter

logger = logging.getLogger(__name__)


def _recover(row_id, now):
    snapshot = MessagingDelivery.objects.get(pk=row_id)
    with tenant_write(snapshot.makerspace_id):
        if snapshot.channel == "whatsapp":
            lock_whatsapp_sender(snapshot.sender_key)
        row = MessagingDelivery.objects.select_for_update().get(pk=row_id)
        if row.status not in {"pending", "sending"}:
            return
        # Do not steal a live provider submission's lease.
        if (row.status == "sending" and row.lease_until and row.lease_until >= now
            and row.created_at >= now - timedelta(days=7)):
            return
        reason = ""
        if row.created_at < now - timedelta(days=7):
            reason = "stale"
        elif row.attempts >= row.max_attempts:
            reason = "attempts_exhausted"
        correlation = MessagingRecipientCorrelation.objects.filter(channel="whatsapp", sender_key=row.sender_key,
            phone_hash=row.recipient_phone_hash).first() if row.channel == "whatsapp" else None
        if correlation and correlation.state != "confirmed" and (correlation.state == "blocked" or (
            correlation.probe_started_at and correlation.probe_started_at <= now - timedelta(hours=72)
        )):
            row.status, row.skip_reason = "skipped", "identity_unconfirmed"
        elif reason:
            observe(row, "failed", at=now, error_code=reason)
        else:
            transaction.on_commit(lambda: schedule_delivery(row.pk), robust=True)
            return True
        row.lease_token = row.lease_until = None
        save_outcome(row, "messaging.delivery_recovered")


def _retention(space_id, now):
    rows = MessagingDelivery.objects.filter(makerspace_id=space_id)
    expired = rows.filter(status="failed", created_at__lt=now - timedelta(days=365)) | rows.exclude(
        status__in=["pending", "sending", "failed"]).filter(created_at__lt=now - timedelta(days=90))
    count = expired.count()
    space = rows.first().makerspace if count else None
    if count:
        with tenant_write(space_id):
            expired.delete()
            record(None, "messaging.deliveries_expired", makerspace=space,
                   meta={"fields": ["context"], "count": count})


def run_sweep():
    now = timezone.now()
    counts = {"enqueued": 0, "skipped": 0, "failed": 0}
    # Retention includes terminal-only tenants, not just those with due sends.
    spaces = MessagingDelivery.objects.order_by().values_list("makerspace_id", flat=True).distinct()
    for space_id in spaces.iterator():
        try:
            with fanout_tenant_write(space_id, operation="messaging_recovery", counts=counts) as permitted:
                if not permitted:
                    continue
                recoverable = (due_filter(now)
                    | Q(status__in=["pending", "sending"], created_at__lt=now - timedelta(days=7))
                    | Q(status="pending", attempts__gte=F("max_attempts")))
                rows = MessagingDelivery.objects.filter(makerspace_id=space_id).filter(recoverable)
                for pk in rows.order_by("pk").values_list("pk", flat=True).iterator():
                    if _recover(pk, now):
                        counts["enqueued"] += 1
                _retention(space_id, now)
        except Exception as exc:
            counts["failed"] += 1
            logger.warning("messaging_sweep_tenant_failed", extra={"makerspace_id": space_id, "failure_type": type(exc).__name__})
    for event in MessagingWebhookEvent.objects.filter(state="pending", next_attempt_at__lte=now).iterator():
        try:
            if event.kind == "status" and event.received_at < now - timedelta(days=30):
                with transaction.atomic():
                    changed = MessagingWebhookEvent.objects.filter(pk=event.pk, state="pending").update(
                        state="abandoned", processed_at=now)
                    if changed:
                        record(None, "messaging.webhook_abandoned", meta={"fields": ["state"], "event_id": event.pk})
            else:
                process_event(event.pk)
        except Exception as exc:
            counts["failed"] += 1
            logger.warning("messaging_webhook_retry_failed", extra={"event_id": event.pk, "failure_type": type(exc).__name__})
    expired = MessagingWebhookEvent.objects.filter(state__in=["processed", "abandoned"], processed_at__lt=now - timedelta(days=30))
    with transaction.atomic():
        count = expired.count()
        if count:
            expired.delete()
            record(None, "messaging.webhooks_expired", meta={"fields": ["payload"], "count": count})
    wipe_retired_credentials()
    return counts
