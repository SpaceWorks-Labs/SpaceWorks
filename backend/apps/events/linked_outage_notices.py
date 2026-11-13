"""A room holding an event was taken out of service: tell the event's organizers (decision 216).

Bookings calls this only through `bookings.event_link_notices.room_out_of_service`, for each
booking a new room outage lists (`maintenance.repairs.notify.bookers_outage`). Nothing is
changed: the event, its booking and their charges stay as they are, and organizers review the
venue in the event's venue panel (which shows the conflict) or replace the booking once staff
cancel it.

Same audiences and the same catalog event as a linked booking change
(`events.linked_booking_changed`): the space's event staff, plus per-event `publish_schedule`
delegates who are not tenant staff. One notice per outage and event (a replacement chain names
one event once), re-checked at send: the outage must still be open, still apply
(`room_outages_apply`) and the booking still hold the room for that event. The copy names the
event and the room; never the booker or the outage reason.
"""

from apps.integrations.notification_outbox import emit
from apps.operations.notifications_p2 import body, fanout, revision, safe_notification, staff_link

from .event_permissions import PUBLISH_SCHEDULE
from .linked_booking_notices import EVENT, _grantees, _on, linked_event

SOURCE = "events.linked_venue_outage"
GRANT_SOURCE = "events.linked_venue_outage_grant"
CHANGE = "room_out_of_service"


def _version(outage, event):
    return revision("RoomOutage", outage.pk, "event", event.pk)


def _copy(outage, event, room):
    blocking = outage.mode == outage.Mode.BLOCK
    back = f" It is expected back {outage.expected_back_at:%Y-%m-%d %H:%M}." if outage.expected_back_at else ""
    subject = f"The venue for {event.title} is out of service"[:200]
    text = (f"{room.name}, which holds the room for {event.title}, is out of service"
            f"{'' if blocking else ' (bookings are still allowed)'}.{back} The event and its booking were not "
            "changed. Review the venue in the event's venue panel.")
    return subject, text


@safe_notification
def notify_organizers(booking, outage):
    from apps.bookings.admission import room_outages_apply
    from apps.integrations.staff_notifications import staff_user_ids_for_feature
    space = booking.space.makerspace
    if not _on(space) or not room_outages_apply(booking.space):
        return None
    event = linked_event(booking.pk, space.pk)
    if event is None or event.makerspace_id != space.pk or event.status not in (
            event.Status.DRAFT, event.Status.PUBLISHED) or event.ends_at <= outage.started_at:
        return None
    subject, text = _copy(outage, event, booking.space)
    rendered = body(subject, text, staff_link(space, f"events?event={event.pk}"))
    version = _version(outage, event)
    context = {"event_id": event.pk, "booking_id": booking.pk, "outage_id": outage.pk, "change": CHANGE}
    result = fanout(row=event, space=space, feature="events", stream="events", event=EVENT, source_kind=SOURCE,
                    revision=version, staff_body=rendered, context=context, staff_context={"event_id": event.pk})
    staff_ids = set(staff_user_ids_for_feature(space, "events", EVENT))
    for person in _grantees(event, staff_ids):
        emit(makerspace=space, recipient=person, feature="events", stream="events", event=EVENT, audience="member",
             dedup_key=f"ev:linked-outage:{event.pk}:{version}:{person.pk}", source_kind=GRANT_SOURCE,
             source_id=str(event.pk), revision=version, subject=event, context=context, rendered=rendered)
    return result


def _live(envelope):
    from apps.bookings.admission import room_outages_apply
    from apps.bookings.models import Booking
    from .models import Event
    event = Event.objects.select_related("makerspace").filter(
        pk=envelope.source_id, makerspace_id=envelope.makerspace_id).first()
    if event is None or envelope.event != EVENT or not _on(event.makerspace):
        return None
    if envelope.context.get("event_id") != event.pk or envelope.context.get("change") != CHANGE:
        return None
    booking = Booking.objects.select_related("space__makerspace").filter(
        pk=envelope.context.get("booking_id"), space__makerspace_id=event.makerspace_id).first()
    if booking is None or not room_outages_apply(booking.space) or linked_event(booking.pk, event.makerspace_id) != event:
        return None
    from apps.maintenance.models import RoomOutage
    outage = RoomOutage.objects.filter(pk=envelope.context.get("outage_id"), room_id=booking.space_id,
                                       ended_at__isnull=True).first()
    if outage is None or envelope.revision != _version(outage, event):
        return None
    return event


def staff_eligible(envelope):
    return envelope.audience == "staff" and _live(envelope) is not None


def grant_eligible(envelope):
    from apps.accounts.models import User
    from . import event_authority
    event = _live(envelope) if envelope.audience == "member" else None
    person = User.objects.filter(pk=envelope.recipient_id).first() if event is not None else None
    return bool(person and event_authority.can(person, event, PUBLISH_SCHEDULE))


def register():
    from apps.integrations.notification_sources import NotificationSource, register_source
    register_source(SOURCE, NotificationSource(staff_eligible))
    register_source(GRANT_SOURCE, NotificationSource(grant_eligible))
