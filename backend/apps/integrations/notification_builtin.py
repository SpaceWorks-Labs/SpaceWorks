"""Reuse mail/inbox/push transports with an explicit personal audience."""
from uuid import NAMESPACE_URL, uuid5

from .notification_providers import ProviderResult


def send_builtin(delivery, rendered):
    envelope = delivery.envelope
    if delivery.channel == "email":
        from .mail_providers.budget_config import free_profile
        if free_profile():
            from .models import EmailLog
            existing = EmailLog.objects.filter(source_kind="notification.envelope", source_id=str(envelope.pk),
                makerspace_id=envelope.makerspace_id, recipient_id=envelope.recipient_id,
                source_metadata__delivery_id=delivery.pk).order_by("pk").first()
            if existing is not None:
                return _free_email_result(existing)
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
        if free_profile():
            return _free_email_result(log)
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


def _free_email_result(log):
    if log.status == "skipped":
        return ProviderResult(False, error_code="skipped")
    if log.status == "sent":
        return ProviderResult(True, f"email:{log.pk}")
    if log.email_retryable:
        return ProviderResult(False, f"email:{log.pk}", retryable=True, error_code="email_deferred")
    return ProviderResult(False, f"email:{log.pk}", error_code="provider_error")


def _push(delivery, rendered):
    from django.utils import timezone
    from .models_push import PlatformPushSettings, PushDevice
    from .push_fcm import PushProviderError, send_fcm
    from .push_apns import send_apns
    config = PlatformPushSettings.load()
    devices = PushDevice.objects.filter(makerspace=delivery.makerspace,
        user_id=delivery.envelope.recipient_id, active=True, device_grant__status="active")
    from .mail_providers.budget_config import free_profile
    if free_profile():
        # Refuse before ANY send if this intent cannot fit the free envelope.
        devices = list(devices.order_by("pk")[:3])
        if len(devices) > 2:
            return ProviderResult(False, error_code="unsupported")
    sent, failed = 0, False
    for device in devices:
        from apps.operations.cloud_jobs.bounded import check
        check()
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
                if free_profile():
                    return ProviderResult(False, retryable=False, error_code="provider_error", ambiguous=True)
                failed = True
        except Exception:
            if free_profile():
                return ProviderResult(False, retryable=False, error_code="provider_error", ambiguous=True)
            failed = True
    return ProviderResult(sent > 0 and not failed, retryable=failed,
                          error_code="provider_error" if failed else "not_configured")
