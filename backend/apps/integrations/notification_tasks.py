"""Recoverable outbox worker; the periodic sweeper also recovers broker outages."""
import logging

from celery import shared_task
from django.db.models import CharField, Exists, OuterRef, Q
from django.db.models.functions import Cast, Coalesce
from django.utils import timezone

from .models_contract import NotificationDelivery, NotificationEnvelope
from .notification_cutover import guarded
from apps.operations.cloud_jobs import bounded
from apps.operations.cloud_jobs.contracts import BudgetExpired, GuardLost

logger = logging.getLogger(__name__)


@shared_task
@guarded(sending=True)
def deliver_envelope(envelope_id):
    bounded.check()
    from .notification_delivery import ensure_deliveries, fallback_if_exhausted, send
    from .notification_outbox import mark_processed, ready
    envelope = NotificationEnvelope.objects.filter(pk=envelope_id).first()
    if envelope is None:
        return
    if envelope.source_kind == "legacy.lifecycle":
        if envelope.processed_at is None:
            from .notification_legacy import recover
            recover(envelope)
        return
    if envelope.processed_at and not runnable_deliveries(envelope.deliveries.all()).exists():
        return
    try:
        if not ready(envelope):
            return
        if envelope.timing_policy == "digest":
            from .notification_digest import collect_digest
            collect_digest(envelope)
            return
        ensure_deliveries(envelope)
        for row in bounded.items(envelope.deliveries.all()):
            send(row.pk)
        fallback_if_exhausted(envelope)
        # A newly created email fallback can be sent in this run.
        for row in bounded.items(envelope.deliveries.filter(channel="email", attempt_count=0)):
            send(row.pk)
        bounded.check()
        mark_processed(envelope)
    except (BudgetExpired, GuardLost):
        raise
    except Exception:
        logger.warning("notification_contract_delivery_failed", extra={"envelope_id": envelope_id})


def runnable_deliveries(rows):
    now = timezone.now()
    return rows.exclude(state="held").filter(
        Q(claim_until__isnull=True) | Q(claim_until__lte=now),
    ).filter(
        Q(state="retrying", next_attempt_at__isnull=True)
        | Q(state="retrying", next_attempt_at__lte=now) | Q(claim_until__lte=now))


@shared_task
def sweep_notification_outbox():
    from django.apps import apps
    if apps.is_installed("apps.notifications"):
        from apps.notifications.browser_firebase_delivery import sweep_pending
        try:
            sweep_pending()
        except Exception:
            logger.exception("browser_firebase_recovery_failed")
    from .notification_ingress import recover
    recover()
    from .notification_media import cleanup_grants
    try:
        cleanup_grants()
    except Exception as exc:
        logger.warning("notification_media_cleanup_unavailable", extra={"failure_type": type(exc).__name__})
    now = timezone.now()
    legs = NotificationDelivery.objects.filter(envelope_id=OuterRef("pk"))
    from .models_document_email import DocumentEmailIntent
    # Only persisted initial/approved permission admits held-only document work.
    # This schedules a worker; reservation still enters the common locked decision.
    pending_documents = DocumentEmailIntent.objects.filter(
        makerspace_id=OuterRef("makerspace_id"), recipient_id=OuterRef("recipient_id"),
        intent_key=OuterRef("dedup_key"), state__in=["initial_pending", "recovery_approved"],
    ).annotate(document_source_id=Cast("document_id", CharField())).filter(
        document_source_id=OuterRef("source_id"))
    # Oldest due work wins even if a sweep runs after the retry delay elapsed.
    due = NotificationEnvelope.objects.filter(
        Q(available_at=None) | Q(available_at__lte=now),
    ).exclude(Q(source_kind="legacy.lifecycle", message_body="") & ~Q(context__has_key="fanout")).alias(
        has_legs=Exists(legs), has_unheld_legs=Exists(legs.exclude(state="held")),
        runnable=Exists(runnable_deliveries(legs)),
        pending_document=Exists(pending_documents),
    ).filter(
        Q(processed_at=None, has_legs=False) | Q(processed_at=None, has_unheld_legs=True) | Q(runnable=True)
        | Q(processed_at=None, source_kind="payments.document", event="document_issued", pending_document=True),
    ).order_by(Coalesce("available_at", "created_at"), "pk")[:200]
    for envelope in due:
        if envelope.source_kind == "payments.document" and envelope.event == "document_issued":
            from .document_email_state import decide, envelope_identity
            decide(**envelope_identity(envelope), event="inspect")
        deliver_envelope.delay(envelope.pk)
