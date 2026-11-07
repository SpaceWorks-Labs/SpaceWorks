"""Personal test messages use the same intent, eligibility, lease and quota path."""
from django.utils.translation import gettext
from uuid import uuid4

from apps.accounts import rbac
from .notification_cutover import CutoverClosed, guarded, sending_allowed
from .notification_sources import NotificationSource, register_source


def eligible(envelope):
    return str(envelope.recipient_id) == envelope.source_id and rbac.can(
        envelope.recipient, rbac.Action.MANAGE_MAKERSPACE, envelope.makerspace_id)


def register():
    register_source("notification.test", NotificationSource(eligible, render))


def render(envelope):
    return {"subject": "Space Works", "text": "Space Works notification delivery test."}


@guarded(mutation=True)
def queue(space, user, channel, *, feature="hardware_requests", event="accepted"):
    from .notification_outbox import emit
    from .notification_delivery import ensure_deliveries
    if not sending_allowed():
        raise CutoverClosed()
    from .notification_catalog import FEATURE_EVENTS
    from rest_framework.exceptions import ValidationError
    if channel not in {"sms", "whatsapp"} or event not in FEATURE_EVENTS.get(feature, ()):
        raise ValidationError(gettext("Choose a known addressed channel and lifecycle event."))
    envelope = emit(makerspace=space, recipient=user, feature=feature, stream=feature, event=event,
        audience="staff", dedup_key=f"diagnostic:{uuid4()}", source_kind="notification.test", source_id=user.pk,
        context={"makerspace.name": space.name, "diagnostic_channel": channel})
    # A diagnostic is addressed only to the caller. It cannot select another user
    # or manufacture consent, preference, endpoint, sender or feature authority.
    ensure_deliveries(envelope)
    return envelope.deliveries.filter(channel=channel).first(), envelope
