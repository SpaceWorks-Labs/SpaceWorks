"""Live source checks for every events envelope (send, retry, deferred release, digest).

The shared layer adds account standing, tenant servability, staff scope, channel gates,
preferences and endpoint consent. These checks add what only events knows: the event still
exists with its module on, the recipient still owns the registration, a delegate still holds
the grant, a campaign is still live with its original sender's authority.
"""

from apps.integrations.notification_sources import NotificationSource, register_source
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable


def _event(envelope):
    from .models import Event
    event = Event.objects.select_related("makerspace").filter(pk=envelope.context.get("event_id")).first()
    return event if (event is not None and is_servable(event.makerspace)
                     and module_enabled(event.makerspace, "events")) else None


def _current_lifecycle(envelope, event):
    from .models import EventRegistration
    from .notification_envelopes import lifecycle_revision
    context = envelope.context
    expected_event = {
        "published": "published", "cancelled": "cancelled", "completed": "completed",
        "series_published": "published", "series_cancelled": "cancelled", "series_completed": "completed",
    }.get(envelope.event)
    if (context.get("notice") != envelope.event
            or context.get("event_status") != event.status
            or (expected_event and event.status != expected_event)):
        return False, None
    registration_id = envelope.context.get("registration_id")
    if not registration_id:
        return envelope.revision == lifecycle_revision(event, None), None
    registration = EventRegistration.objects.filter(pk=registration_id, event=event).first()
    valid = bool(registration and envelope.revision == lifecycle_revision(event, registration))
    return valid, registration


def lifecycle_eligible(envelope):
    from .notification_envelopes import _owner_allowed
    event = _event(envelope)
    if event is None:
        return False
    current, registration = _current_lifecycle(envelope, event)
    if not current:
        return False
    if envelope.audience == "staff":
        if envelope.makerspace_id == event.makerspace_id:
            return True
        # Organizer spaces: the organization link and its kill switch are re-read live.
        from .notifications import _organizer_spaces
        return _organizer_spaces(event.pk, event.makerspace_id).filter(makerspace_id=envelope.makerspace_id).exists()
    return bool(envelope.audience == "requester" and registration
                and registration.member_id == envelope.recipient_id
                and _owner_allowed(envelope.makerspace, envelope.event))


def grant_eligible(envelope):
    from .grant_recipients import holds_registration_grant
    event = _event(envelope)
    return bool(event and _current_lifecycle(envelope, event)[0]
                and envelope.makerspace_id == event.makerspace_id
                and holds_registration_grant(envelope.recipient_id, event))


def reminder_eligible(envelope):
    from django.utils import timezone
    from .models import Event, EventRegistration
    from .notification_envelopes import _owner_allowed
    event = _event(envelope)
    if event is None or event.status != Event.Status.PUBLISHED or event.starts_at <= timezone.now():
        return False
    if event.starts_at.isoformat() != envelope.context.get("starts_at"):
        return False  # rescheduled: the new start gets its own reminder
    if envelope.audience != "requester" or not _owner_allowed(envelope.makerspace, envelope.event):
        return False
    return EventRegistration.objects.filter(
        pk=envelope.context.get("registration_id"), event=event, member_id=envelope.recipient_id,
        status=EventRegistration.Status.REGISTERED).exists()


def broadcast_eligible(envelope):
    from .broadcast_channels import personal_source_eligible
    return personal_source_eligible(envelope)


def certificate_eligible(envelope):
    from .certificates.notifications import eligible
    return eligible(envelope)


SOURCES = {
    "events.lifecycle": NotificationSource(lifecycle_eligible),
    "events.grant_staff": NotificationSource(grant_eligible),
    "events.reminder": NotificationSource(reminder_eligible),
    "events.broadcast": NotificationSource(broadcast_eligible),
    "events.certificate": NotificationSource(certificate_eligible),
}


def register_event_sources():
    for kind, source in SOURCES.items():
        register_source(kind, source)
