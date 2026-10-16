"""Reuse mail/inbox/push transports with an explicit personal audience."""
from uuid import NAMESPACE_URL, uuid5

from .notification_providers import ProviderResult


def send_builtin(delivery, rendered):
    envelope = delivery.envelope
    if delivery.channel == "email":
        from apps.hardware_requests.notifications_p2_email import render_email
        rendered = render_email(envelope, rendered)
        from .dispatch import dispatch_email
        from .timing_dispatch import RELEASING
        # The envelope already handled quiet hours/digest and source eligibility.
        # Deferring again in EmailLog would detach the message from that authority.
        token = RELEASING.set(True)
        try:
            log = dispatch_email(makerspace=envelope.makerspace,
                to_email=envelope.recipient.email, recipient_id=envelope.recipient_id,
                feature=envelope.feature, stream=envelope.stream, event=envelope.event,
                audience=envelope.audience, subject=rendered.get("subject", "Space Works"),
                source_kind="notification.envelope", source_id=envelope.pk,
                source_metadata={"delivery_id": delivery.pk},
                text_body=rendered.get("text", ""), html_body=rendered.get("html", ""), sync=True)
        finally:
            RELEASING.reset(token)
        if log.status == "skipped":
            return ProviderResult(False, error_code="skipped")
        return ProviderResult(log.status == "sent", f"email:{log.pk}",
                              retryable=log.status == "failed", error_code="provider_error")
    if delivery.channel == "in_app":
        from apps.notifications.models_inbox import NotificationInboxRow
        from apps.notifications.inbox import safe_link
        row, _ = NotificationInboxRow.objects.get_or_create(makerspace=envelope.makerspace,
            user_id=envelope.recipient_id, event_key=uuid5(NAMESPACE_URL, envelope.dedup_key),
            defaults={"feature": envelope.feature, "event": envelope.event,
                      "title": rendered.get("subject", "Space Works")[:200],
                      "summary": rendered.get("text", "")[:2000], "link": safe_link(rendered.get("link", ""))})
        return ProviderResult(True, f"inbox:{row.pk}")
    if delivery.channel == "native_push":
        return _push(delivery, rendered)
    return ProviderResult(False, error_code="not_configured")


def _push(delivery, rendered):
    from django.utils import timezone
    from .models_push import PlatformPushSettings, PushDevice
    from .push_fcm import PushProviderError, send_fcm
    from .push_apns import send_apns
    config = PlatformPushSettings.load()
    devices = PushDevice.objects.filter(makerspace=delivery.makerspace,
        user_id=delivery.envelope.recipient_id, active=True, device_grant__status="active")
    sent, failed = 0, False
    for device in devices:
        try:
            data = {"feature": delivery.envelope.feature, "event": delivery.envelope.event}
            if device.provider == "fcm" and config.fcm_configured:
                send_fcm(config, device.get_token(), "Space Works", rendered.get("text", "")[:300], data)
            elif device.provider == "apns" and config.apns_configured:
                send_apns(config, device.get_token(), device.environment, "Space Works", rendered.get("text", "")[:300], data)
            else:
                continue
            sent += 1
        except PushProviderError as exc:
            if exc.invalid_token:
                PushDevice.objects.filter(pk=device.pk).update(active=False, invalidated_at=timezone.now())
            else:
                failed = True
        except Exception:
            failed = True
    return ProviderResult(sent > 0 and not failed, retryable=failed,
                          error_code="provider_error" if failed else "not_configured")
