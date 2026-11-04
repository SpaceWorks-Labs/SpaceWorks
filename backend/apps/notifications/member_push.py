"""Canonical envelope adapter; inbox writes and old task IDs have no send authority."""
import logging
from uuid import NAMESPACE_URL, uuid5

from django.db.models import Q

from apps.accounts import rbac
from apps.integrations.models_push import PlatformPushSettings, PushDevice
from apps.integrations.notification_cutover import boundary, sending_allowed
from apps.integrations.notification_providers import ProviderResult
from apps.notifications.envelope_push_leases import claim, due_deliveries, hold_expired, skip
from apps.notifications.member_push_policy import device_allowed, recipient_allowed
from apps.notifications.models_inbox import NotificationInboxRow
from apps.notifications.models_push import MemberPushDelivery
from apps.tenant_migration.gate_runtime import boundary_tenant_write

logger = logging.getLogger(__name__)


def enqueue_member_push(row_id):
    """Import shim: pre-cutover inbox producers cannot create another push intent."""
    return False


def deliver_row(row_id):
    """Queued legacy tasks are inert, including colliding numeric IDs."""
    return False


def send_envelope_push(delivery, rendered):
    with boundary():
        if not sending_allowed():
            return ProviderResult(False, error_code="unavailable")
        with boundary_tenant_write(delivery.makerspace_id):
            delivery.refresh_from_db()
            if (delivery.channel != "native_push" or delivery.historical
                    or delivery.makerspace_id != delivery.envelope.makerspace_id):
                return ProviderResult(False, error_code="skipped")
            if delivery.state in {"sent", "accepted", "delivered", "read"}:
                return ProviderResult(True)
            if delivery.state == "held":
                return ProviderResult(False, ambiguous=True, error_code="ambiguous_timeout")
            if delivery.state == "skipped" or (delivery.state == "failed" and not delivery.retryable):
                return ProviderResult(False, error_code="skipped")
            envelope = delivery.envelope
            if not recipient_allowed(envelope):
                return ProviderResult(False, error_code="skipped")
            return _deliver(delivery, envelope, rendered)


def _deliver(parent, envelope, rendered):
    children = MemberPushDelivery.objects.filter(envelope_delivery=parent)
    key = uuid5(NAMESPACE_URL, envelope.dedup_key)
    inbox = rbac.scope_notification_policy(
        NotificationInboxRow.objects.all(), makerspace_id=envelope.makerspace_id,
    ).filter(user_id=envelope.recipient_id, event_key=key).first()
    # Revisit former devices too: reassignment cannot leave runnable work.
    devices = rbac.scope_notification_policy(
        PushDevice.objects.all(), makerspace_id=envelope.makerspace_id,
    ).filter(Q(user_id=envelope.recipient_id) | Q(pk__in=children.values("push_device_id"))).select_related(
        "device_grant__registration",
    )
    settings_row = PlatformPushSettings.load()
    for device in devices.iterator():
        child, _ = children.get_or_create(envelope_delivery=parent, push_device=device, defaults={
            "inbox_row": inbox, "platform": device.device_grant.registration.platform,
            "provider_source": "platform",
        })
        target = MemberPushDelivery.objects.filter(pk=child.pk, envelope_delivery_id=parent.pk)
        if not device_allowed(device, envelope):
            skip(target, "recipient_or_device_ineligible")
            continue
        token = claim(target)
        if token is not None:
            from .envelope_push_transport import send_child
            send_child(envelope, rendered, settings_row, device, inbox, target, token, key)
    hold_expired(children)
    if children.filter(status="held").exists():
        return ProviderResult(False, ambiguous=True, error_code="ambiguous_timeout")
    if children.filter(status="sending").exists() or due_deliveries(children).exists():
        return ProviderResult(False, retryable=True, error_code="unavailable")
    # One accepted device is useful even if another device has an invalid token.
    if children.filter(status="sent").exists():
        return ProviderResult(True)
    return ProviderResult(False, error_code="skipped")


def enqueue_parent(parent_id):
    from apps.integrations.notification_tasks import deliver_envelope
    try:
        from apps.integrations.models_contract import NotificationDelivery
        envelope_id = NotificationDelivery.objects.get(pk=parent_id).envelope_id
        deliver_envelope.delay(envelope_id)
        return True
    except Exception as exc:
        logger.warning("push_parent_enqueue_failed", extra={
            "delivery_id": parent_id, "failure_type": type(exc).__name__,
        })
        return False
