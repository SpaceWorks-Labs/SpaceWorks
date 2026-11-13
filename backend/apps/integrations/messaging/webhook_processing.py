"""Durable callback inbox: insert first, process in a savepoint, retry early events."""
import logging
from datetime import datetime
from datetime import timezone as dt_timezone

from django.db import transaction

from apps.integrations.models import MessagingDelivery, MessagingWebhookEvent
from apps.tenant_migration.gate_runtime import tenant_write

from .correlation import confirm_probe
from .outcomes import observe, save_outcome
from .stops import annotate_stop, suppress_recipient

logger = logging.getLogger(__name__)


def provider_timestamp(value):
    try:
        return datetime.fromtimestamp(int(value), tz=dt_timezone.utc) if value not in (None, "") else None
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def _delivery_for_status(event):
    data = event.payload
    rows = MessagingDelivery.objects.filter(provider=event.provider, sender_key=event.sender_key)
    if event.makerspace_id is not None:
        rows = rows.filter(makerspace_id=event.makerspace_id)
    delivery = rows.filter(provider_message_id=data.get("message_id") or "__missing__").first()
    opaque = str(data.get("delivery_id", ""))
    if (delivery is None and event.provider == "meta" and opaque.isascii() and opaque.isdigit()
        and len(opaque) <= 19 and 0 < int(opaque) <= 9223372036854775807):
        delivery = rows.filter(pk=int(opaque), channel="whatsapp").first()
    return delivery


@transaction.atomic
def _protect_status_event(pk):
    """Commit shared sender protection once, before any tenant-gated work.

    The payload marker is server-owned inbox bookkeeping. A retry must not
    suppress again after a newer in-app re-consent lifted this event's effect.
    """
    event = MessagingWebhookEvent.objects.select_for_update().filter(pk=pk, provider="twilio", kind="status").first()
    if (event is None or event.state != "pending"
        or event.payload.get("protection_applied")
        or event.payload.get("error_code") not in {"21610", "21211", "21614"}):
        return
    delivery = _delivery_for_status(event)
    phone = event.payload.get("phone_hash") or (delivery.recipient_phone_hash if delivery else "")
    if not phone:
        return  # An early callback retries when the delivery has been recorded.
    suppress_recipient(event.channel, event.sender_key, phone,
        reason="provider_opt_out" if event.payload["error_code"] == "21610" else "permanent_failure")
    event.payload = {**event.payload, "protection_applied": True}
    event.save(update_fields=["payload"])


def _status(event):
    data = event.payload
    delivery = _delivery_for_status(event)
    if delivery is None:
        return False
    event.makerspace_id = delivery.makerspace_id
    with tenant_write(delivery.makerspace_id):
        row = MessagingDelivery.objects.select_for_update().get(pk=delivery.pk)
        if row.provider_message_id and row.provider_message_id != data.get("message_id"):
            return True
        row.provider_message_id = data["message_id"]
        if event.channel == "whatsapp":
            confirm_probe(row, alias_hash=data.get("alias_hash", ""), phone_hash=data.get("phone_hash", ""))
        error_code = data.get("error_code", "")
        if event.provider == "meta" and (error_code.startswith("132") or error_code in {"131026", "131047"}):
            error_code = "template_rejected"
        observe(row, data.get("status", ""), at=provider_timestamp(data.get("timestamp")),
                error_code=error_code, billed_segments=data.get("billed_segments"))
        save_outcome(row, "messaging.provider_status")
        event.makerspace_id = row.makerspace_id
    return True


def process_event(pk):
    """Compatibility recovery imports the old inbox without mutating legacy outcomes."""
    event = MessagingWebhookEvent.objects.get(pk=pk)
    return accept_event(provider=event.provider, channel=event.channel, sender_key=event.sender_key,
        makerspace_id=event.makerspace_id, dedupe_id=event.dedupe_id, kind=event.kind, payload=event.payload)


def accept_event(**values):
    from apps.integrations.notification_ingress import accept_legacy
    return accept_legacy(**values)


def _annotate_stop_safely(pk):
    try:
        annotate_stop(pk)
    except Exception as exc:
        logger.warning("messaging_stop_consent_annotation_failed", extra={"event_id": pk, "failure_type": type(exc).__name__})
