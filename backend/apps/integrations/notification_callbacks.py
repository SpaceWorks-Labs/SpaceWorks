"""Authenticated provider facts update only the exact sender/generation/attempt."""
from django.db import transaction
from django.utils import timezone

from .models_contract import NotificationDelivery as Delivery
from .notification_cutover import guarded


@guarded(mutation=True)
def apply_callback(configuration, event, *, observation=None):
    """Only call with an event returned by this integration's verify_callback."""
    from .notification_delivery import RANK, SUCCESS, fallback_if_exhausted
    if event.state not in RANK or not event.provider_id:
        return False
    with transaction.atomic():
        sender_key = getattr(configuration, "sender_key", "")
        if configuration.channel == "whatsapp" and sender_key:
            from .messaging.locks import lock_whatsapp_sender
            lock_whatsapp_sender(sender_key)
        rows = Delivery.objects.select_for_update().filter(
            makerspace=configuration.makerspace, channel=configuration.channel,
            provider=configuration.provider, integration_generation=configuration.generation,
            integration_identity=configuration.integration_identity,
        )
        if sender_key:
            rows = rows.filter(sender_key=sender_key)
        rows = rows.filter(pk=event.delivery_id) if event.delivery_id else rows.filter(provider_id=event.provider_id)
        changed = False
        for row in rows:
            if event.delivery_attempt is not None and row.attempt_count != event.delivery_attempt:
                continue
            if row.provider_id and row.provider_id != event.provider_id:
                continue
            if observation and not row.recipient_phone_hash and observation.get("phone_hash"):
                row.recipient_phone_hash = observation["phone_hash"]
                Delivery.objects.filter(pk=row.pk).update(recipient_phone_hash=row.recipient_phone_hash)
            row.provider_id = event.provider_id
            from .notification_provider_references import remember
            remember(row)
            now = timezone.now()
            if event.state == "failed":
                Delivery.objects.filter(pk=row.pk).update(failed_at=row.failed_at or now)
            if observation and row.channel == "whatsapp":
                from .messaging.correlation import confirm_canonical_probe
                confirm_canonical_probe(row, alias_hash=observation.get("alias_hash", ""),
                    phone_hash=observation.get("phone_hash", ""))
                Delivery.objects.filter(pk=row.pk).update(recipient_alias_hash=row.recipient_alias_hash)
            # A read/delivered acknowledgement cannot be undone by a late failure.
            if event.state == "failed" and (row.state in {"accepted", "sent", "held"}
                    or (row.state == "retrying" and row.claim_until)):
                row.state, row.retryable = "failed", False
            elif RANK[event.state] > RANK[row.state] and event.state in SUCCESS:
                row.state, row.retryable = event.state, False
            else:
                continue
            row.next_attempt_at = None
            row.claim_until = None
            row.provider_id = event.provider_id
            if event.state in {"accepted", "sent", "delivered", "read"}:
                field = event.state + "_at"
                Delivery.objects.filter(pk=row.pk).update(**{field: getattr(row, field) or now})
            row.save(update_fields=["state", "provider_id", "retryable", "next_attempt_at", "claim_until", "updated_at"])
            from apps.audit.services import record
            record(None, "notification.delivery_observed", makerspace=row.makerspace, target=row,
                meta={"channel": row.channel, "state": row.state})
            changed = True
    if changed and event.state == "failed":
        for row in rows:
            fallback_if_exhausted(row.envelope)
        from .notification_outbox import enqueue
        for row in rows:
            transaction.on_commit(lambda pk=row.envelope_id: enqueue(pk), robust=True)
    return changed
