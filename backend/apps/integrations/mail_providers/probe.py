"""Explicit operator-triggered round-trip, using the same policy/budget boundary."""

from django.utils.translation import gettext
from dataclasses import dataclass

from django.core.validators import validate_email


@dataclass(frozen=True)
class MailProbeResult:
    accepted: bool
    code: str
    log_id: int


def probe_mail(*, actor, recipient, makerspace=None):
    """I calls only from the existing authorized/audited settings-test operation.

    This confirms provider acceptance; an operator must confirm inbox delivery.
    Never invoked by readiness, health polling or an unattended tick.
    """
    validate_email(recipient)
    from apps.integrations.dispatch import dispatch_email
    from apps.audit import services as audit
    log = dispatch_email(to_email=recipient, subject=gettext("Space Works email test"),
        text_body=gettext("This is a Space Works delivery test. Confirm it arrived in your inbox."),
        makerspace=makerspace, stream="account", event="email_test", audience="staff",
        connection="makerspace" if makerspace else "platform", sync=True, persist_body=False)
    accepted = log.status == log.Status.SENT
    audit.record(actor, "email.transport_tested", makerspace=makerspace, target=log,
                 meta={"accepted": accepted})
    return MailProbeResult(accepted, "provider_accepted" if accepted else "email_probe_not_accepted", log.pk)
