"""Reuse mail/inbox/push transports with an explicit personal audience."""
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
        from apps.notifications.inbox import write_envelope_inbox
        row = write_envelope_inbox(envelope, rendered)
        return ProviderResult(True, f"inbox:{row.pk}")
    if delivery.channel == "native_push":
        return _push(delivery, rendered)
    return ProviderResult(False, error_code="not_configured")


_native_push_sender = None


def register_native_push_sender(sender):
    """P registers its per-device lease adapter from AppConfig.ready()."""
    global _native_push_sender
    if _native_push_sender is not None and _native_push_sender is not sender:
        raise ValueError("Duplicate native-push envelope adapter")
    _native_push_sender = sender


def _push(delivery, rendered):
    if _native_push_sender is None:
        return ProviderResult(False, error_code="not_configured")
    return _native_push_sender(delivery, rendered)
