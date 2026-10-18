"""Recoverable outbox worker; the periodic sweeper also recovers broker outages."""
import logging

from celery import shared_task
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from .models_contract import NotificationDelivery, NotificationEnvelope
from .notification_cutover import guarded

logger = logging.getLogger(__name__)


@shared_task
@guarded(sending=True)
def deliver_envelope(envelope_id):
    from .notification_delivery import ensure_deliveries, fallback_if_exhausted, send
    from .notification_outbox import ready
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
        for row in envelope.deliveries.all():
            send(row.pk)
        fallback_if_exhausted(envelope)
        # A newly created email fallback can be sent in this run.
        for row in envelope.deliveries.filter(channel="email", attempt_count=0):
            send(row.pk)
        NotificationEnvelope.objects.filter(pk=envelope.pk).update(processed_at=timezone.now())
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
    from .notification_ingress import recover
    recover()
    from .notification_media import cleanup_grants
    try:
        cleanup_grants()
    except Exception as exc:
        logger.warning("notification_media_cleanup_unavailable", extra={"failure_type": type(exc).__name__})
    now = timezone.now()
    legs = NotificationDelivery.objects.filter(envelope_id=OuterRef("pk"))
    due = NotificationEnvelope.objects.filter(
        Q(available_at=None) | Q(available_at__lte=now),
    ).exclude(source_kind="legacy.lifecycle", message_body="").alias(
        has_legs=Exists(legs), has_unheld_legs=Exists(legs.exclude(state="held")),
        runnable=Exists(runnable_deliveries(legs)),
    ).filter(
        Q(processed_at=None, has_legs=False) | Q(processed_at=None, has_unheld_legs=True) | Q(runnable=True),
    ).order_by("pk").values_list("pk", flat=True)[:200]
    for pk in due:
        deliver_envelope.delay(pk)
