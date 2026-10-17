"""Recoverable outbox worker; the periodic sweeper also recovers broker outages."""
import logging

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from .models_contract import NotificationEnvelope

logger = logging.getLogger(__name__)


@shared_task
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
    if envelope.processed_at and not envelope.deliveries.filter(state="retrying").exists():
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


@shared_task
def sweep_notification_outbox():
    from .notification_media import cleanup_grants
    try:
        cleanup_grants()
    except Exception as exc:
        logger.warning("notification_media_cleanup_unavailable", extra={"failure_type": type(exc).__name__})
    now = timezone.now()
    due = NotificationEnvelope.objects.filter(
        Q(available_at=None) | Q(available_at__lte=now),
    ).exclude(source_kind="legacy.lifecycle", message_body="").filter(
        Q(processed_at=None) | Q(deliveries__state="retrying", deliveries__next_attempt_at__lte=now)
        | Q(deliveries__claim_until__lte=now)).order_by("pk").distinct().values_list("pk", flat=True)[:200]
    for pk in due:
        deliver_envelope.delay(pk)
