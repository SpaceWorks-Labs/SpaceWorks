"""One device call, live policy recheck, sanitized errors and fenced token cleanup."""
import logging

from django.db import transaction
from django.utils import timezone

from apps.integrations.push import send_device_push
from apps.integrations.push_fcm import PushProviderError
from apps.integrations.push_payload import push_data
from .envelope_push_leases import MAX_ATTEMPTS, complete
from .member_push_policy import device_allowed, recipient_allowed

logger = logging.getLogger(__name__)


def send_child(envelope, rendered, settings_row, device, inbox, target, token, event_key):
    # A claim is not authorization: logout/deletion/rotation can win after enqueue.
    device.refresh_from_db()
    device.device_grant.refresh_from_db()
    device.device_grant.registration.refresh_from_db()
    if not recipient_allowed(envelope) or not device_allowed(device, envelope):
        complete(target, token, status="skipped", error="live_eligibility_changed")
        return
    try:
        data = push_data(event_id=event_key, makerspace_id=envelope.makerspace_id,
                         feature=envelope.feature, event=envelope.event,
                         inbox_row_id=inbox.pk if inbox else None, link=rendered.get("link", ""))
        sent = send_device_push(settings_row, device, envelope.makerspace.name[:64],
                                str(rendered.get("text", ""))[:178], data)
        complete(target, token, status="sent" if sent else "skipped",
                 error="" if sent else "provider_not_configured")
    except Exception as exc:
        invalid = isinstance(exc, PushProviderError) and exc.invalid_token
        # Shared adapters wrap network failures. Only their explicit configuration
        # or HTTP rejection results prove that this call was not accepted.
        known = isinstance(exc, PushProviderError) and str(exc) in {
            "FCM configuration is unavailable.", "FCM authorization failed.",
            "APNs configuration is unavailable.", "FCM delivery failed.", "APNs delivery failed.",
        }
        ambiguous = not invalid and not known
        # A dead token is a terminal fact about this destination, never a transient one.
        retry = known and not invalid and target.filter(attempts__lt=MAX_ATTEMPTS).exists()
        with transaction.atomic():
            changed = complete(target, token, status="held" if ambiguous else "failed",
                               retryable=retry, error="invalid_token" if invalid else
                               "unknown_provider_outcome" if ambiguous else "provider_rejected")
            if changed and invalid:
                # A registration can rotate/reassign while the provider is in
                # flight. Invalidate only the exact destination that was attempted.
                type(device).objects.filter(pk=device.pk, makerspace_id=device.makerspace_id,
                    user_id=device.user_id, device_grant_id=device.device_grant_id,
                    token_fingerprint=device.token_fingerprint, provider=device.provider,
                    environment=device.environment).update(active=False, invalidated_at=timezone.now())
        logger.warning("envelope_push_failed", extra={
            "push_device_id": device.pk, "invalid_token": invalid, "ambiguous": ambiguous,
            "failure_type": type(exc).__name__,
        })
