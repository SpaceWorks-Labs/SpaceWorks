"""Platform SMS resolution.

Credentials live in the ``PlatformSmsSettings`` DB singleton rather than env vars,
matching ``PlatformEmailSettings``/``PlatformSocialAuthSettings``: an operator
configures SMS from ``/control/`` without a redeploy, and no new variable has to be
threaded through four compose services, both installers and ``.env.example``.

SMS here is **platform-scoped, for auth/OTP only**. Login resolves before a
makerspace is selected, so there is no tenant to bill or to read credentials from.
Per-makerspace SMS for reminders is a notification channel and is a separate
concern with separate credentials.
"""

import logging

from apps.integrations.sms.base import SmsProvider

logger = logging.getLogger(__name__)

__all__ = ["SmsProvider", "get_sms_provider", "sms_configured", "send_sms", "send_sms_now"]


def _settings_row():
    from apps.integrations.models_sms import PlatformSmsSettings

    return PlatformSmsSettings.objects.filter(pk=1).first()


def get_sms_provider():
    """Return the configured provider, or None when SMS is not set up.

    Returning None (rather than raising) is what keeps the whole feature dormant:
    every caller treats None as "SMS is off" and the surfaces omit themselves.
    """
    row = _settings_row()
    if row is None or not row.is_enabled:
        return None
    if row.provider == "twilio":
        from apps.integrations.sms.twilio import TwilioSmsProvider

        provider = TwilioSmsProvider(row)
    else:
        # An unknown stored provider is a misconfiguration, not a crash: the choices
        # are validated at the form, so this can only be reached by a hand-edited row
        # or a downgrade. Fail closed and stay quiet in the payload.
        logger.warning("sms_provider_unknown", extra={"provider": row.provider})
        return None
    return provider if provider.is_configured() else None


def sms_configured() -> bool:
    return get_sms_provider() is not None


def send_sms(*, to: str, body: str) -> bool:
    """Hand a verification SMS to the Celery worker (sealed, never stored); True means accepted for delivery.

    Inline only where no worker exists (eager Celery, free profile) or inside a worker already.
    """
    from apps.integrations.transient_mail import queue_sms
    if queue_sms(to=to, body=body):
        return True
    return send_sms_now(to=to, body=body) == "sent"


def send_sms_now(*, to: str, body: str) -> str:
    """The provider call itself: runs in the worker task (or inline where no worker exists)."""
    from apps.integrations.models_tracking import SmsSendLog

    status = "failed"
    try:
        provider = get_sms_provider()
        if provider is None:
            status = "skipped"
        else:
            status = "sent" if provider.send(to=to, body=body) else "failed"
    except Exception as exc:
        logger.warning("sms_send_raised", extra={"error_class": type(exc).__name__})
    SmsSendLog.objects.create(purpose="authentication", provider_source="platform", status=status)
    return status
