"""The test a space's own SMTP account must pass before it carries mail (parity E-B8, A19).

Sends ONE synchronous message through the space's own account (bypassing the verification gate, which is the
point), records the outcome in the audit log without any credential, and stamps the verification fingerprint only
when the server accepted the message. A failure leaves the account unverified, so mail keeps using the platform
path. Never invoked by readiness, health polling or an unattended tick.
"""

import logging
from dataclasses import dataclass

from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.utils import timezone
from django.utils.translation import gettext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SpaceSmtpProbeResult:
    accepted: bool
    code: str
    verified_at: object = None


def probe_space_smtp(*, actor, makerspace, recipient) -> SpaceSmtpProbeResult:
    from apps.audit import services as audit
    from apps.integrations.email import makerspace_mail_connection
    from apps.integrations.space_smtp_gate import mark_verified, own_smtp_in_use

    validate_email(recipient)
    if not own_smtp_in_use(makerspace):
        return SpaceSmtpProbeResult(False, "smtp_not_configured")
    code = "provider_accepted"
    try:
        connection, from_email = makerspace_mail_connection(makerspace, skip_smtp_gate=True)
        message = EmailMultiAlternatives(
            subject=gettext("Space Works email test"),
            body=gettext("This is a Space Works delivery test. Confirm it arrived in your inbox."),
            from_email=from_email, to=[recipient], connection=connection)
        if connection is None or message.send(fail_silently=False) != 1:
            code = "smtp_probe_not_accepted"
    except Exception as exc:  # Static code only; the exception text can carry the host or login.
        logger.warning("space_smtp_probe_failed", extra={"makerspace_id": makerspace.pk, "error_class": type(exc).__name__})
        code = "smtp_probe_failed"
    accepted = code == "provider_accepted"
    now = timezone.now() if accepted else None
    if accepted:
        mark_verified(makerspace, now)
    audit.record(actor, "email.smtp_probe_ran", makerspace=makerspace, target=makerspace,
                 meta={"accepted": accepted, "code": code})
    return SpaceSmtpProbeResult(accepted, code, now)
