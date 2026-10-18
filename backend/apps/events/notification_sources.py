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
        return (envelope.source_id == f"e{event.pk}"
                and envelope.revision == lifecycle_revision(event, None)), None
    registration = EventRegistration.objects.filter(pk=registration_id, event=event).first()
    valid = bool(registration and envelope.source_id == f"r{registration.pk}"
                 and envelope.revision == lifecycle_revision(event, registration))
    return valid, registration


def _owner_space(registration):
    return registration.registered_via_makerspace_id or registration.event.makerspace_id


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
                and envelope.makerspace_id == _owner_space(registration)
                and registration.member_id == envelope.recipient_id
                and _owner_allowed(envelope.makerspace, envelope.event))


def grant_eligible(envelope):
    from .grant_recipients import holds_registration_grant
    event = _event(envelope)
    return bool(event and envelope.audience == "member" and _current_lifecycle(envelope, event)[0]
                and envelope.makerspace_id == event.makerspace_id
                and holds_registration_grant(envelope.recipient_id, event))


def reminder_eligible(envelope):
    from django.utils import timezone
    from .models import Event, EventRegistration
    from .notification_envelopes import _owner_allowed
    from apps.makerspaces.reminder_policy import reminder_offsets
    event = _event(envelope)
    if event is None or event.status != Event.Status.PUBLISHED or event.starts_at <= timezone.now():
        return False
    if event.starts_at.isoformat() != envelope.context.get("starts_at"):
        return False  # rescheduled: the new start gets its own reminder
    if envelope.audience != "requester" or not _owner_allowed(envelope.makerspace, envelope.event):
        return False
    if (type(envelope.context.get("offset_seconds")) is not int
            or envelope.context["offset_seconds"] not in reminder_offsets(envelope.makerspace, "event")):
        return False
    row = EventRegistration.objects.filter(
        pk=envelope.source_id, event=event, member_id=envelope.recipient_id,
        status=EventRegistration.Status.REGISTERED).first()
    return bool(row and row.pk == envelope.context.get("registration_id")
                and _owner_space(row) == envelope.makerspace_id)


def broadcast_eligible(envelope):
    from rest_framework.exceptions import APIException
    from .broadcasts import authorize, registrations
    from .models_broadcasts import EventBroadcast
    campaign = EventBroadcast.objects.select_related("event__makerspace", "makerspace", "created_by").filter(
        pk=envelope.context.get("campaign_id"), makerspace_id=envelope.makerspace_id).first()
    if campaign is None or campaign.status not in {"queued", "sending", "sent", "failed"}:
        return False
    try:
        authorize(campaign, campaign.created_by)
    except APIException:
        return False
    return registrations(campaign).filter(member_id=envelope.recipient_id).exists()


def certificate_eligible(envelope):
    from .models import EventAttendanceCertificate
    expected = {"certificate_ready": "active", "certificate_revoked": "revoked"}.get(envelope.event)
    event = _event(envelope)
    if not event or not expected or envelope.audience != "requester":
        return False
    row = EventAttendanceCertificate.objects.select_related("registration__event").filter(
        pk=envelope.source_id, status=expected, revision=envelope.revision,
        registration__event=event, registration__member_id=envelope.recipient_id).first()
    return bool(row and row.pk == envelope.context.get("certificate_id")
                and _owner_space(row.registration) == envelope.makerspace_id)


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
