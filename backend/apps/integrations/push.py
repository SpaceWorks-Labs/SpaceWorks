import logging

from django.utils import timezone

from apps.integrations.models_push import PlatformPushSettings, PushDevice
from apps.integrations.push_fcm import PushProviderError, send_fcm
from apps.integrations.staff_notifications import staff_user_ids_for_feature
from apps.integrations.push_payload import push_data

logger = logging.getLogger(__name__)


def send_device_push(settings_row, device, title, body, data):
    """One provider call shared by staff fan-out and leased member delivery."""
    data = {key: str(value) for key, value in data.items()}
    if device.provider == PushDevice.Provider.FCM:
        if not settings_row.fcm_configured:
            return False
        send_fcm(settings_row, device.get_token(), title, body, data)
    elif device.provider == PushDevice.Provider.APNS:
        if not settings_row.apns_configured:
            return False
        from apps.integrations.push_apns import send_apns

        send_apns(settings_row, device.get_token(), device.environment, title, body, data)
    else:
        return False
    return True


def deactivate_push_device(device):
    PushDevice.objects.filter(pk=device.pk, makerspace_id=device.makerspace_id).update(
        active=False, invalidated_at=timezone.now(),
    )


def push_configured():
    try:
        row = PlatformPushSettings.load()
        return bool(
            (row.fcm_configured and row.get_fcm_service_account())
            or (row.apns_configured and row.get_apns_private_key())
        )
    except Exception:
        return False


def deliver_native_push(log):
    # Additive master switch (plan A6): the platform credential check below still runs,
    # so enabling the feature on an unconfigured platform delivers nothing.
    from apps.makerspaces.platform import feature_enabled

    if log.makerspace_id and not feature_enabled(log.makerspace, "mobile.push"):
        return False
    settings_row = PlatformPushSettings.load()
    if not (settings_row.fcm_configured or settings_row.apns_configured):
        return False
    from apps.integrations.destinations import NotificationScope

    user_ids = staff_user_ids_for_feature(
        log.makerspace,
        log.feature,
        event=log.event,
        scope=NotificationScope.from_dict((log.payload or {}).get("scope")),
    )
    from apps.notifications.preferences import personal_enabled
    user_ids = [uid for uid in user_ids if personal_enabled(
        log.makerspace, uid, log.feature, "native_push", event=log.event,
    )]
    devices = PushDevice.objects.filter(
        makerspace=log.makerspace, user_id__in=user_ids, active=True,
        device_grant__status="active", user__is_active=True, user__access_status="active",
        device_grant__registration__status="approved",
        device_grant__registration__makerspace__isnull=True,
    ).select_related("device_grant")
    transient_failure = False
    for device in devices:
        try:
            data = push_data(
                event_id=(log.payload or {}).get("event_key") or str(log.pk),
                makerspace_id=log.makerspace_id, feature=log.feature, event=log.event,
                link=(log.payload or {}).get("link", ""),
            )
            send_device_push(settings_row, device, log.makerspace.name[:64], log.text_body, data)
        except PushProviderError as exc:
            if exc.invalid_token:
                deactivate_push_device(device)
            else:
                transient_failure = True
            logger.warning("native_push_provider_failed", extra={
                "push_device_id": device.pk, "provider": device.provider,
                "invalid_token": exc.invalid_token,
            })
        except Exception:
            transient_failure = True
            logger.warning("native_push_delivery_failed", extra={
                "push_device_id": device.pk, "provider": device.provider,
            })
    if transient_failure:
        raise PushProviderError("Native push delivery failed.")
    return True
