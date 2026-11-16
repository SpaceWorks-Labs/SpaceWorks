"""A person's volunteer and mentor shifts as calendar entries (release 2 L18, `events.shifts_feed`).

READS `events/contributions/models_shifts.py` (lane L21a owns it; nothing here writes it).
Only the person's own APPROVED signups, for shifts whose programme switch is on (volunteer
shifts need `events.volunteering`, mentor office hours `events.mentoring`), in events that
are not drafts. An entry carries the shift's task, zone and times and the event's title --
never another volunteer, a requirement answer or a contact.
"""

from datetime import timezone as dt_timezone

KIND_FEATURES = {"volunteer": "events.volunteering", "office_hours": "events.mentoring"}
LIMIT = 500


def shift_signups(space, user):
    from apps.makerspaces.platform import feature_enabled

    from .contributions.models_shifts import EventShiftSignup
    from .models import Event

    kinds = [kind for kind, key in KIND_FEATURES.items() if feature_enabled(space, key)]
    return (EventShiftSignup.objects.filter(makerspace=space, member=user, state="approved", shift__kind__in=kinds)
            .exclude(shift__event__status=Event.Status.DRAFT)
            .select_related("shift", "shift__event").order_by("shift__starts_at", "pk"))


def shift_component(signup):
    from icalendar import Event as ICalEvent

    shift, event = signup.shift, signup.shift.event
    component = ICalEvent()
    stamp = event.calendar_updated_at.astimezone(dt_timezone.utc)
    component.add("uid", f"shift-{signup.pk}@spaceworks")
    label = "Mentor office hours" if shift.kind == "office_hours" else (shift.task or "Volunteer shift")
    component.add("summary", f"{label}: {event.title}")
    if shift.zone or event.location:
        component.add("location", shift.zone or event.location)
    component.add("dtstart", shift.starts_at.astimezone(dt_timezone.utc))
    component.add("dtend", shift.ends_at.astimezone(dt_timezone.utc))
    component.add("dtstamp", stamp)
    component.add("last-modified", stamp)
    component.add("sequence", int(shift.version) + int(event.calendar_sequence))
    cancelled = event.status == event.Status.CANCELLED
    component.add("status", "CANCELLED" if cancelled else "CONFIRMED")
    return component


def add_shifts(calendar, space, user, *, limit=LIMIT):
    for signup in shift_signups(space, user)[:limit]:
        calendar.add_component(shift_component(signup))
    return calendar


def render_shift_calendar(space, user):
    from .services_calendar import _calendar

    calendar = _calendar(f"{space.name} - My shifts")
    return add_shifts(calendar, space, user).to_ical()
