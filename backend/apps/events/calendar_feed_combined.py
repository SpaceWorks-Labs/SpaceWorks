"""The combined personal feed (C-14e) and the public listed-events feed (C-14f), release 2 L18.

Combined: ONE person's own items in one space -- their bookings (when `bookings` is on),
their event registrations (when `events` is on; the same rows and join-link rule as the
member event feed) and their approved shifts (`calendar_feed_shifts`). Nobody else's
booking, registration or contact is ever read. Busy blocks (`bookings.busy_overlay_ics`)
appear only where a room outage, machine repair or closure meets one of their own upcoming
bookings. Their own open loans appear as "return due" items (`request_workflow` on) and their own
active membership term as a "membership ends" day (`membership` on, never a lifetime term), so
nothing in the feed is about anyone else. A person who staffs machines here also gets the dated maintenance schedules of the
machines in their scope (P3-1), gated by `machines.maintenance`, the
`maintenance.calendar_feed` switch (decision 221(g)) and the maintenance feed's own scope,
so a member with no machine scope sees none.

Public: the space's LISTED published events (the L1 listing gate, `listed_q`): unlisted,
private and offline events never appear, cancelled ones retire as CANCELLED for a month.
"""

from datetime import timedelta

from django.utils import timezone
from django.utils.translation import gettext

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
    """The person's own bookings here (unsliced), or None when bookings is off."""
    from apps.accounts import rbac
    from apps.bookings.models import Booking
    from apps.makerspaces.platform import module_enabled
    from apps.separability.registry import runtime_active

    if not runtime_active("bookings") or not module_enabled(space, "bookings"):
        return None
    return rbac.scope_personal_bookings(user, Booking.objects.select_related("space").filter(
        member=user, space__makerspace=space), makerspace_id=space.pk)


def _maintenance(space, user):
    """P3-1: dated maintenance on machines in the person's scope; empty for everyone else.

    Decision 221(g): `maintenance.calendar_feed` governs maintenance in this feed too, so
    switching the maintenance feed off removes it everywhere a calendar carries it."""
    from apps.makerspaces.folded_capabilities import MACHINES_MAINTENANCE, capability_on
    from apps.makerspaces.platform import feature_enabled
    from apps.separability.registry import runtime_active

    if not (runtime_active("maintenance") and runtime_active("machines")
            and capability_on(space, MACHINES_MAINTENANCE)
            and feature_enabled(space, "maintenance.calendar_feed")):
        return []
    from apps.maintenance.calendar_feed import schedule_components

    return schedule_components(user, space)[:LIMIT]


def _loan_due_components(space, user):
    """The person's own issued loans with a due time (open item A28); empty while lending is off."""
    from icalendar import Event as ICalEvent

    from apps.accounts import rbac
    from apps.hardware_requests.models import HardwareRequest
    from apps.makerspaces.platform import module_enabled
    from apps.separability.registry import runtime_active

    if not runtime_active("hardware_requests") or not module_enabled(space, "request_workflow"):
        return []
    rows = rbac.scope_by_borrower(user, HardwareRequest.objects.all(), makerspace=space).filter(
        status__in=(HardwareRequest.Status.ISSUED, HardwareRequest.Status.PARTIALLY_RETURNED),
        return_due_at__isnull=False).order_by("return_due_at", "pk")[:LIMIT]
    components = []
    for row in rows:
        component = ICalEvent()
        component.add("uid", f"loan-due-{row.pk}@spaceworks")
        component.add("dtstamp", timezone.now())
        component.add("dtstart", row.return_due_at)
        component.add("dtend", row.return_due_at + timedelta(minutes=15))
        component.add("summary", gettext("Return due: loan #%(id)s") % {"id": row.pk})
        components.append(component)
    return components


def _term_end_components(space, user):
    """The person's own active, non-lifetime membership term end (open item A28)."""
    from icalendar import Event as ICalEvent

    from apps.makerspaces.models import MembershipTerm
    from apps.makerspaces.platform import module_enabled

    if not module_enabled(space, "membership"):
        return []
    terms = MembershipTerm.objects.filter(
        membership__makerspace=space, membership__user=user, membership__status="active",
        status=MembershipTerm.Status.ACTIVE, ends_at__gte=timezone.now()).exclude(plan_type="lifetime")
    components = []
    for term in terms.order_by("ends_at", "pk")[:10]:
        if term.is_lifetime:
            continue
        component = ICalEvent()
        component.add("uid", f"term-end-{term.pk}@spaceworks")
        component.add("dtstamp", timezone.now())
        day = timezone.localtime(term.ends_at, timezone.get_default_timezone()).date()
        component.add("dtstart", day)
        component.add("dtend", day + timedelta(days=1))
        component.add("summary", gettext("Membership ends"))
        components.append(component)
    return components


def render_combined_calendar(space, user):
    from apps.makerspaces.platform import module_enabled

    from .calendar_alarms import add_member_alarms
    from .calendar_feed_shifts import add_shifts
    from .member_history import registrations_for_space
    from .models import Event, EventRegistration
    from .services_calendar import _calendar, _event_component

    calendar = _calendar(f"{space.name} - My calendar")
    bookings = _bookings(space, user)
    if bookings is not None:
        from apps.bookings.busy_overlay_ics import busy_components

        since = timezone.now() - timedelta(days=90)
        for booking in bookings.filter(ends_at__gte=since).order_by("starts_at", "pk")[:LIMIT]:
            calendar.add_component(_booking_component(booking))
        for component in busy_components(bookings):
            calendar.add_component(component)
    for component in _maintenance(space, user):
        calendar.add_component(component)
    for component in (*_loan_due_components(space, user), *_term_end_components(space, user)):
        calendar.add_component(component)
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
