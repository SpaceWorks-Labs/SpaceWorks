"""The combined personal feed (C-14e) and the public listed-events feed (C-14f), release 2 L18.

Combined: ONE person's own items in one space -- their bookings (when `bookings` is on),
their event registrations (when `events` is on; the same rows and join-link rule as the
member event feed) and their approved shifts (`calendar_feed_shifts`). Nobody else's
booking, registration or contact is ever read.

Public: the space's LISTED published events (the L1 listing gate, `listed_q`): unlisted,
private and offline events never appear, cancelled ones retire as CANCELLED for a month.
"""

from datetime import timedelta

from django.utils import timezone

LIMIT = 500


def _booking_component(booking):
    from icalendar import Event as ICalEvent

    component = ICalEvent()
    component.add("uid", f"booking-{booking.public_token}@spaceworks")
    component.add("dtstamp", booking.calendar_updated_at)
    component.add("last-modified", booking.calendar_updated_at)
    component.add("sequence", booking.calendar_sequence)
    component.add("dtstart", booking.starts_at)
    component.add("dtend", booking.ends_at)
    component.add("summary", booking.space.name)
    component.add("status", "CANCELLED" if booking.status in ("cancelled", "rejected") else
                  "TENTATIVE" if booking.status == "pending" else "CONFIRMED")
    return component


def _bookings(space, user):
    from apps.accounts import rbac
    from apps.bookings.models import Booking
    from apps.makerspaces.platform import module_enabled
    from apps.separability.registry import runtime_active

    if not runtime_active("bookings") or not module_enabled(space, "bookings"):
        return []
    rows = rbac.scope_personal_bookings(user, Booking.objects.select_related("space").filter(
        member=user, space__makerspace=space), makerspace_id=space.pk)
    since = timezone.now() - timedelta(days=90)
    return rows.filter(ends_at__gte=since).order_by("starts_at", "pk")[:LIMIT]


def render_combined_calendar(space, user):
    from apps.makerspaces.platform import module_enabled

    from .calendar_alarms import add_member_alarms
    from .calendar_feed_shifts import add_shifts
    from .member_history import registrations_for_space
    from .models import Event, EventRegistration
    from .services_calendar import _calendar, _event_component

    calendar = _calendar(f"{space.name} - My calendar")
    for booking in _bookings(space, user):
        calendar.add_component(_booking_component(booking))
    if module_enabled(space, "events"):
        rows = registrations_for_space(space, user).select_related("event").order_by("event__starts_at", "pk")
        for registration in rows[:LIMIT]:
            component = _event_component(registration.event, registration=registration)
            if (registration.status == EventRegistration.Status.REGISTERED
                    and registration.event.status == Event.Status.PUBLISHED):
                add_member_alarms(component, space, registration.event.title)
            calendar.add_component(component)
        add_shifts(calendar, space, user)
    return calendar.to_ical()


def render_public_listing(space):
    from .models import Event
    from .services_calendar import _calendar, _event_component
    from .website_visibility import listed_q

    calendar = _calendar(f"{space.name} - Events")
    since = timezone.now() - timedelta(days=30)
    rows = Event.objects.filter(listed_q(), makerspace=space, ends_at__gte=since,
                                status__in=(Event.Status.PUBLISHED, Event.Status.CANCELLED)).order_by("starts_at", "pk")
    for event in rows[:LIMIT]:
        calendar.add_component(_event_component(event))
    return calendar.to_ical()
