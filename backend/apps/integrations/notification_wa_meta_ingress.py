"""Compatibility journal adapter and canonical transient-failure replay helper."""
from datetime import timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts import rbac
from apps.audit import services as audit
from .models_contract import NotificationDelivery
from .notification_delivery import MAX_ATTEMPTS, apply_callback
from .notification_providers import CallbackEvent
from .notification_wa_meta_http import error_result
from .notification_cutover import guarded


def apply_item(configuration, request, index, item):
    """Compatibility import seam; there is no synchronous alternative writer."""
    from .notification_wa_meta_callbacks import items, verified_payload
    from .notification_wa_journal import accept_meta_item
    payload = verified_payload(configuration, request)
    if payload is None:
        raise ValidationError({"proof": "Provider verification failed."})
    batch = items(configuration, payload)
    if type(index) is not int or not 0 <= index < len(batch) or batch[index] != item:
        raise ValidationError({"proof": "Invalid authenticated batch item."})
    return accept_meta_item(configuration, request, index, item)


def _delivery_rows(configuration, row):
    return rbac.scope_notification_policy(NotificationDelivery.objects.all(),
        makerspace_id=configuration.makerspace_id).filter(channel="whatsapp", provider="meta",
        integration_generation=configuration.generation, integration_identity=configuration.integration_identity,
        provider_id=row["id"])


@guarded(mutation=True)
def _retry_failure(configuration, row, event):
    """No premature email fallback on an authenticated transient failure callback."""
    changed = False
    rows = rbac.scope_notification_policy(NotificationDelivery.objects.all(),
        makerspace_id=configuration.makerspace_id).filter(channel="whatsapp", provider="meta",
        integration_generation=configuration.generation, integration_identity=configuration.integration_identity)
    rows = rows.filter(pk=event.delivery_id) if event.delivery_id else rows.filter(provider_id=row["id"])
    for delivery in rows.select_for_update():
        if event.delivery_attempt is not None and delivery.attempt_count != event.delivery_attempt:
            continue
        if delivery.provider_id and delivery.provider_id != row["id"]:
            continue
        if delivery.state not in {"accepted", "sent", "held"} and not (delivery.state == "retrying" and delivery.claim_until):
            continue
        if delivery.attempt_count >= MAX_ATTEMPTS:
            changed = apply_callback(configuration, CallbackEvent(provider_id=row["id"], state="failed", delivery_id=delivery.pk)) or changed
            continue
        error = row["errors"][0]
        delivery.state, delivery.retryable = "retrying", True
        delivery.provider_id = row["id"]
        delivery.last_error = error_result(400, {"error": error}).error_code
        delivery.next_attempt_at = timezone.now() + timedelta(seconds=min(30 * 2 ** delivery.attempt_count, 3600))
        delivery.claim_until = None
        delivery.save(update_fields=["state", "provider_id", "retryable", "last_error", "next_attempt_at", "claim_until", "updated_at"])
        changed = True
    return changed


def _delivery_audit(configuration, row):
    deliveries = _delivery_rows(configuration, row).filter(state__in=[row["status"], "retrying"])
    for delivery in deliveries:
        if row["status"] == "failed":
            errors = row.get("errors", [])
            error = errors[0] if isinstance(errors, list) and errors and isinstance(errors[0], dict) else {}
            # CallbackEvent has no error fields. Preserve only the fixed code
            # beside the state chosen by the shared layer or bounded retry helper.
            code = error_result(400, {"error": error}).error_code
            deliveries.filter(pk=delivery.pk).update(last_error=code, updated_at=timezone.now())
        audit.record(None, "notification.whatsapp_delivery_updated", makerspace=configuration.makerspace,
            target=delivery, meta={"channel": "whatsapp", "state": delivery.state,
                                   "generation": configuration.generation})
