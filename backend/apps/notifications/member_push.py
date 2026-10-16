"""Best-effort member transport coupled intentionally to durable inbox content."""

import logging

from django.db import transaction
from django.db.models import Q

from apps.accounts import rbac
from apps.backup.not_restored import TenantNotRestored
from apps.integrations.models_push import PlatformPushSettings, PushDevice
from apps.integrations.push import deactivate_push_device, send_device_push
from apps.integrations.push_fcm import PushProviderError
from apps.integrations.push_payload import push_data
from apps.notifications.member_push_leases import MAX_ATTEMPTS, claim, complete, skip
from apps.notifications.member_push_policy import device_allowed, global_enabled, recipient_allowed
from apps.notifications.models_inbox import NotificationInboxRow
from apps.notifications.models_push import MemberPushDelivery
from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
from apps.tenant_migration.gate_runtime import boundary_tenant_write

logger = logging.getLogger(__name__)


def enqueue_member_push(row_id):
    from apps.notifications.tasks import deliver_member_push

    try:
        deliver_member_push.delay(row_id)
        return True
    except Exception as exc:
        logger.warning("member_push_enqueue_failed", extra={
            "inbox_row_id": row_id, "failure_type": type(exc).__name__,
        })
        return False


def deliver_row(row_id):
    space_id = NotificationInboxRow.objects.filter(pk=row_id).values_list("makerspace_id", flat=True).first()
    if space_id is None:
        return False
    # Dedicated source-gate connection protects writes without transacting provider I/O.
    try:
        with boundary_tenant_write(space_id):
            row = rbac.scope_notification_policy(
                NotificationInboxRow.objects.select_related("makerspace"), makerspace_id=space_id,
            ).filter(pk=row_id).first()
            if row is None or not global_enabled(row):
                return False
            return _deliver_row(row)
    except (SourceMigrationGateClosed, TenantNotRestored):
        logger.info("member_push_source_unavailable", extra={"makerspace_id": space_id})
        return False


def _deliver_row(row):
    allowed = recipient_allowed(row)
    deliveries = rbac.scope_notification_policy(
        MemberPushDelivery.objects.all(), makerspace_id=row.makerspace_id,
        field="inbox_row__makerspace_id",
    ).filter(inbox_row=row)
    # Include prior destinations so reassignment/revocation terminates their old work.
    devices = rbac.scope_notification_policy(
        PushDevice.objects.all(), makerspace_id=row.makerspace_id,
    ).filter(Q(user_id=row.user_id) | Q(pk__in=deliveries.values("push_device_id"))).select_related(
        "device_grant__registration",
    )
    candidates = []
    for device in devices.iterator():
        delivery, _ = deliveries.get_or_create(inbox_row=row, push_device=device)
        if not allowed or not device_allowed(device, row):
            skip(_target(row, delivery.pk), "recipient_or_device_ineligible")
            continue
        candidates.append((delivery.pk, device))
    if not candidates:
        return False
    settings_row = PlatformPushSettings.load()
    retry = False
    for delivery_id, device in candidates:
        target = _target(row, delivery_id)
        token = claim(target)
        if token is None:
            continue
        retry = _send(row, settings_row, device, target, token) or retry
    return retry


def _target(row, delivery_id):
    # Ownership was resolved through the scoped inbox above. Keep UPDATE predicates
    # on this table: a joined queryset becomes an IN subquery whose snapshot can let
    # concurrent workers both pass a status check instead of rechecking the live row.
    return MemberPushDelivery.objects.filter(pk=delivery_id, inbox_row_id=row.pk)


def _send(row, settings_row, device, target, token):
    try:
        data = push_data(event_id=row.event_key, makerspace_id=row.makerspace_id,
                         feature=row.feature, event=row.event, inbox_row_id=row.pk, link=row.link)
        # Attribute access is deliberate: the model decrypts the stored member summary.
        sent = send_device_push(settings_row, device, row.makerspace.name[:64], row.summary[:178], data)
        complete(target, token, status="sent" if sent else "skipped",
                 error="" if sent else "provider_not_configured")
        return False
    except Exception as exc:
        invalid = isinstance(exc, PushProviderError) and exc.invalid_token
        with transaction.atomic():
            changed = complete(target, token, status="failed", exhausted=invalid,
                               error="invalid_token" if invalid else type(exc).__name__)
            if changed and invalid:
                deactivate_push_device(device)
        logger.warning("member_push_delivery_failed", extra={
            "inbox_row_id": row.pk, "push_device_id": device.pk, "provider": device.provider,
            "invalid_token": invalid, "failure_type": type(exc).__name__,
        })
        return bool(changed and not invalid and target.filter(attempts__lt=MAX_ATTEMPTS).exists())
