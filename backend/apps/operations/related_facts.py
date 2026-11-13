"""Read-only, side-by-side facts for one event or one booking (decision 216 item 13).

The subject is resolved inside the URL makerspace and authorized at VIEW through its
own owner (event or booking authority). Every section then re-checks its own source's
module and authority; the response exists only if at least one section survives.
Nothing here writes: registration, attendance, arrival, presence and machine sessions
stay independent records, each labelled with the model it came from.
"""

from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.makerspaces.platform import feature_enabled
from apps.makerspaces.servability import servable_queryset
from .related_facts_sections import machine_sessions_section, presence_section

REGISTRATION_SOURCE = "events.EventRegistration"
ATTENDANCE_SOURCE = "events.EventCheckInEvent"
ARRIVAL_SOURCE = "bookings.BookingCheckInEvent"


def _space(makerspace_id):
    return get_object_or_404(servable_queryset(), pk=makerspace_id)


def _require_or_404(authority, actor, resource, permission):
    """Authority failure reads as "not found": a foreign space id must not confirm that an event or booking
    exists there (open item B2, no existence oracle). Module-off refusals keep their own answer."""
    try:
        authority.require(actor, resource, permission)
    except PermissionDenied:
        raise NotFound()


def _finish(subject, sections):
    present = {key: value for key, value in sections.items() if value is not None}
    if not present:
        raise NotFound()
    return {"subject": subject, **present}


def _registrations(event):
    from apps.events.models import EventRegistration
    counts = dict(EventRegistration.objects.filter(event=event).order_by().values_list("status").annotate(n=Count("pk")))
    return {"source": REGISTRATION_SOURCE,
            "by_status": {status: counts.get(status, 0) for status in EventRegistration.Status.values}}


def _attendance(event):
    from apps.events.models import EventCheckInEvent, EventRegistration
    records = EventCheckInEvent.objects.filter(event=event, makerspace_id=event.makerspace_id)
    by_source = dict(records.order_by().values_list("source").annotate(n=Count("pk")))
    return {
        "source": ATTENDANCE_SOURCE,
        "attended_registrations": EventRegistration.objects.filter(
            event=event, status=EventRegistration.Status.ATTENDED).count(),
        "check_in_records": sum(by_source.values()),
        "registrations_with_check_in": records.order_by().values("registration_id").distinct().count(),
        "check_in_records_by_source": by_source,
    }


def event_facts(actor, makerspace_id, event_id):
    from apps.events import event_authority
    from apps.events.event_permissions import CHECK_IN, MANAGE_REGISTRATIONS, VIEW
    from apps.events.models import Event
    space = _space(makerspace_id)
    event = get_object_or_404(Event.objects.select_related("makerspace"), makerspace=space, pk=event_id)
    _require_or_404(event_authority, actor, event, VIEW)
    registrations = event_authority.can(actor, event, MANAGE_REGISTRATIONS)
    attendance = registrations or event_authority.can(actor, event, CHECK_IN)
    subject = {"kind": "event", "id": event.pk, "starts_at": event.starts_at, "ends_at": event.ends_at}
    return _finish(subject, {
        "registrations": _registrations(event) if registrations else None,
        "attendance": _attendance(event) if attendance else None,
        "presence": presence_section(actor, space, event.starts_at, event.ends_at, event=event),
    })


def _arrival(booking):
    from apps.bookings.models import BookingCheckInEvent
    actions = dict(BookingCheckInEvent.objects.filter(booking=booking).order_by().values_list("action").annotate(n=Count("pk")))
    return {
        "source": ARRIVAL_SOURCE,
        "booking_status": booking.status,
        "arrived_at": booking.arrived_at,
        "departed_at": booking.departed_at,
        "arrival_confirmations": actions.get("arrived", 0),
        "arrival_reversals": actions.get("reversed", 0),
    }


def booking_facts(actor, makerspace_id, booking_id):
    from apps.bookings import booking_authority
    from apps.bookings.booking_permissions import CHECK_IN, MANAGE_RESERVATIONS, VIEW
    from apps.bookings.models import Booking
    space = _space(makerspace_id)
    booking = get_object_or_404(Booking.objects.select_related("space__makerspace", "space__machine__makerspace"),
                                space__makerspace=space, pk=booking_id)
    resource = booking.space
    _require_or_404(booking_authority, actor, resource, VIEW)
    arrival = (feature_enabled(space, "bookings.checkin")
               and (booking_authority.can(actor, resource, CHECK_IN)
                    or booking_authority.can(actor, resource, MANAGE_RESERVATIONS)))
    machine = resource.machine if resource.machine_id and resource.machine.makerspace_id == space.pk else None
    start, end = booking.starts_at, booking.ends_at
    subject = {"kind": "booking", "id": booking.pk, "starts_at": start, "ends_at": end,
               "machine_id": machine.pk if machine else None}
    return _finish(subject, {
        "arrival": _arrival(booking) if arrival else None,
        "presence": presence_section(actor, space, start, end, person_id=booking.member_id),
        "machine_sessions": machine_sessions_section(actor, machine, start, end, person_id=booking.member_id),
    })
