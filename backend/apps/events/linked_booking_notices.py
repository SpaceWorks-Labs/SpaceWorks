"""A linked venue booking changed: tell the event's organizers (decision 216).

Bookings calls this only through `bookings.event_link_notices`, after a booking that holds a
room for an event (the decision booking or a replacement descending from it) was moved,
cancelled, rejected or restored after a cancellation (221(f)). The event itself is never
changed. Two audiences, each re-checked at every send:

* the space's event staff (Event/Space Managers, with their selections, mutes and rooms);
* per-event delegates holding `publish_schedule` on the event or its series who are not tenant
  staff, and event managers of the event's organizer organizations (who may work from another
  space, decision 221(f)), all re-checked live through `event_authority`.

The copy names the event, the booking number and the room -- never the booker. One notice per
booking calendar revision; silent while Events or Bookings is off.
"""

from apps.integrations.notification_outbox import emit
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable
from apps.operations.notifications_p2 import body, fanout, revision, safe_notification, staff_link

from .event_permissions import PUBLISH_SCHEDULE

SOURCE = "events.linked_booking_change"
GRANT_SOURCE = "events.linked_booking_change_grant"
EVENT = "linked_booking_changed"
WORDS = {"moved": "was moved to a new time", "cancelled": "was cancelled", "rejected": "was rejected",
         # Decision 221(f): undoing a cancellation is a change the organizers must hear about too.
         "restored": "was restored after a cancellation",
         # Decision 223 G4: approving the venue tells the organizers the room is secured.
         "confirmed": "was approved, so the venue is confirmed"}


def _on(space):
    return is_servable(space) and module_enabled(space, "events") and module_enabled(space, "bookings")


def linked_event(booking_id, makerspace_id):
    """The event whose retained decision names this booking or an ancestor of it, or None."""
    from apps.bookings.models import Booking
    from .booking_decision_replacement import MAX_CHAIN
    from .models_booking_decision import EventBookingDecision
    for _step in range(MAX_CHAIN):
        if booking_id is None:
            return None
        decision = EventBookingDecision.objects.select_related("event__makerspace").filter(
            booking_id=booking_id, makerspace_id=makerspace_id).first()
        if decision is not None:
            return decision.event
        booking_id = Booking.objects.filter(pk=booking_id).values_list("replaces_id", flat=True).first()
    return None


def _grantees(event, exclude):
    from apps.accounts.models import User
    from django.db.models import Q
    from . import event_authority
    from .models import EventStaffGrant
    from apps.organizations.models import OrganizationMembership
    rows = EventStaffGrant.objects.filter(
        Q(event=event) | Q(series_id=event.series_id, series__isnull=False),
        makerspace_id=event.makerspace_id, revoked_at__isnull=True, permissions__contains=[PUBLISH_SCHEDULE])
    # Decision 221(f): event managers of the event's ORGANIZER organizations, who may run events
    # from another space and hold no role here; `event_authority.can` re-checks their authority.
    organizers = OrganizationMembership.objects.filter(
        organization__organized_events__event=event, organization__is_active=True,
        status=OrganizationMembership.Status.ACTIVE)
    people = User.objects.filter(Q(pk__in=rows.values("user_id")) | Q(pk__in=organizers.values("user_id")),
                                 is_active=True, access_status="active",
                                 is_tenant_dump_stub=False).exclude(pk__in=exclude).order_by("pk")[:200]
    return [person for person in people if event_authority.can(person, event, PUBLISH_SCHEDULE)]


@safe_notification
def notify_organizers(booking, change):
    from apps.integrations.staff_notifications import staff_user_ids_for_feature
    space = booking.space.makerspace
    if change not in WORDS or not _on(space):
        return None
    event = linked_event(booking.pk, space.pk)
    if event is None or event.makerspace_id != space.pk:
        return None
    subject = f"The venue booking for {event.title} changed"[:200]
    text = (f"Booking #{booking.pk} in {booking.space.name}, which holds the room for {event.title}, "
            f"{WORDS[change]}. The event was not changed. Review the venue in the event's venue panel.")
    rendered = body(subject, text, staff_link(space, f"events?event={event.pk}"))
    version = revision("Booking", booking.pk, change, booking.calendar_sequence)
    context = {"event_id": event.pk, "booking_id": booking.pk, "change": change}
    result = fanout(row=event, space=space, feature="events", stream="events", event=EVENT, source_kind=SOURCE,
                    revision=version, staff_body=rendered, context=context, staff_context={"event_id": event.pk})
    staff_ids = set(staff_user_ids_for_feature(space, "events", EVENT))
    for person in _grantees(event, staff_ids):
        emit(makerspace=space, recipient=person, feature="events", stream="events", event=EVENT, audience="member",
             dedup_key=f"ev:linked-booking:{event.pk}:{version}:{person.pk}", source_kind=GRANT_SOURCE,
             source_id=str(event.pk), revision=version, subject=event, context=context, rendered=rendered)
    return result


def _live(envelope):
    from apps.bookings.models import Booking
    from .models import Event
    event = Event.objects.select_related("makerspace").filter(
        pk=envelope.source_id, makerspace_id=envelope.makerspace_id).first()
    if event is None or envelope.event != EVENT or not _on(event.makerspace):
        return None
    if envelope.context.get("event_id") != event.pk or envelope.context.get("change") not in WORDS:
        return None
    booking = Booking.objects.filter(pk=envelope.context.get("booking_id"),
                                     space__makerspace_id=event.makerspace_id).first()
    if booking is None or linked_event(booking.pk, event.makerspace_id) != event:
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
