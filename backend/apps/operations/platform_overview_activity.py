"""Machines, events, bookings and membership blocks of the platform overview (#183A)."""

from django.db.models import DurationField, ExpressionWrapper, F

from apps.makerspaces.platform import module_enabled
from apps.operations.platform_overview_blocks import (
    Block, Metric, count_by_space, hours, in_window, sum_by_space,
)

#: Machine job statuses folded into the columns a platform reader needs.
JOB_GROUPS = (
    ("jobs_open", "Jobs waiting", ("pending", "changes_requested", "quoted", "accepted")),
    ("jobs_in_progress", "Jobs running", ("in_progress",)),
    ("jobs_done", "Jobs done", ("completed", "collected")),
    ("jobs_failed", "Jobs failed or not collected", ("failed", "uncollected")),
    ("jobs_cancelled", "Jobs cancelled or rejected", ("cancelled", "rejected")),
)


def _machines(ids, window, now):
    from apps.machines.models import Machine, MachineServiceRequest, MachineSession

    jobs = in_window(MachineServiceRequest.objects.filter(makerspace_id__in=ids), "created_at", window)
    sessions = in_window(MachineSession.objects.filter(makerspace_id__in=ids), "started_at", window)
    data = {
        "machines": count_by_space(Machine.objects.filter(makerspace_id__in=ids, is_active=True)),
        "sessions": count_by_space(sessions),
        "session_hours": {space: hours(minutes) for space, minutes in
                          sum_by_space(sessions, "duration_minutes").items()},
    }
    for key, _label, statuses in JOB_GROUPS:
        data[key] = count_by_space(jobs.filter(status__in=statuses))
    return data


def _utilisation(per_space, totals, window):
    """Session hours over (active machines x window hours); None for all time."""
    def ratio(session_hours, machines):
        if not window.hours or not machines:
            return None
        return round(session_hours * 100 / (machines * window.hours), 1)

    rows = {space: ratio(values.get("session_hours") or 0, values.get("machines") or 0)
            for space, values in per_space.items() if values is not None}
    return rows, ratio(totals.get("session_hours") or 0, totals.get("machines") or 0)


MACHINES = Block(
    key="machines", label="Machines", switches=("machines",),
    gate=lambda space: module_enabled(space, "machines"),
    metrics=(
        Metric("machines", "Active machines", timing="snapshot"),
        *(Metric(key, label) for key, label, _statuses in JOB_GROUPS),
        Metric("sessions", "Machine sessions"),
        Metric("session_hours", "Session hours", unit="hours"),
        Metric("utilisation", "Utilisation", unit="percent"),
    ),
    collect=_machines, derive={"utilisation": _utilisation},
)


def _events(ids, window, now):
    from apps.events.models import Event, EventCheckInEvent, EventRegistration

    events = Event.objects.filter(makerspace_id__in=ids)
    held = in_window(events.filter(status__in=("published", "completed"), ends_at__lte=now), "ends_at", window)
    registrations = EventRegistration.objects.filter(event__makerspace_id__in=ids).exclude(
        status__in=("cancelled", "rejected"))
    check_ins = in_window(EventCheckInEvent.objects.filter(makerspace_id__in=ids), "attended_at", window)
    return {
        "events_held": count_by_space(held),
        "events_upcoming": count_by_space(events.filter(status="published", starts_at__gt=now)),
        "registrations": count_by_space(in_window(registrations, "created_at", window), "event__makerspace_id"),
        "check_ins": count_by_space(check_ins, distinct="registration_id"),
        "hackathon_submissions": _submissions(ids, window),
    }


def _submissions(ids, window):
    """One per submitted STAGE entry on staged events (#178); one per project on events without stages."""
    from apps.events.submissions.models_projects import HackathonSubmission
    from apps.events.submissions.models_stages import SubmissionStage, SubmissionStageEntry

    staged = SubmissionStage.objects.filter(event__makerspace_id__in=ids).values("event_id")
    excluded = ("draft", "withdrawn")
    entries = SubmissionStageEntry.objects.filter(
        stage__event__makerspace_id__in=ids, current_snapshot__isnull=False, submitted_at__isnull=False,
    ).exclude(submission__state__in=excluded)
    projects = HackathonSubmission.objects.filter(
        event__makerspace_id__in=ids, submitted_at__isnull=False,
    ).exclude(state__in=excluded).exclude(event_id__in=staged)
    per_space = count_by_space(in_window(entries, "submitted_at", window), "stage__event__makerspace_id")
    for space_id, n in count_by_space(in_window(projects, "submitted_at", window), "event__makerspace_id").items():
        per_space[space_id] = per_space.get(space_id, 0) + n
    return per_space


EVENTS = Block(
    key="events", label="Events", switches=("events",),
    gate=lambda space: module_enabled(space, "events"),
    metrics=(
        Metric("events_held", "Events held"),
        Metric("events_upcoming", "Upcoming events", timing="snapshot"),
        Metric("registrations", "Registrations"),
        Metric("check_ins", "People checked in"),
        # Per stage entry where an event has submission stages, so a two-stage project counts twice.
        Metric("hackathon_submissions", "Hackathon submissions (per stage; per project without stages)"),
    ),
    collect=_events,
)

BOOKED = ("confirmed", "completed", "no_show")


def _bookings(ids, window, now):
    from apps.bookings.models import Booking

    bookings = in_window(Booking.objects.filter(space__makerspace_id__in=ids), "starts_at", window)
    booked = bookings.filter(status__in=BOOKED)
    length = ExpressionWrapper(F("ends_at") - F("starts_at"), output_field=DurationField())
    space = "space__makerspace_id"
    return {
        "bookings": count_by_space(booked, space),
        "booked_hours": {key: hours(value) for key, value in sum_by_space(booked, length, space).items()},
        "no_shows": count_by_space(bookings.filter(status="no_show"), space),
        "cancelled": count_by_space(bookings.filter(status="cancelled"), space),
        "pending": count_by_space(Booking.objects.filter(space__makerspace_id__in=ids, status="pending"), space),
    }


BOOKINGS = Block(
    key="bookings", label="Bookings", switches=("bookings",),
    gate=lambda space: module_enabled(space, "bookings"),
    metrics=(
        Metric("bookings", "Bookings"),
        Metric("booked_hours", "Booked hours", unit="hours"),
        Metric("no_shows", "No-shows"),
        Metric("cancelled", "Cancelled bookings"),
        Metric("pending", "Awaiting approval", timing="snapshot"),
    ),
    collect=_bookings,
)


def _membership(ids, window, now):
    from apps.makerspaces.models_membership_terms import MembershipTerm

    terms = MembershipTerm.objects.filter(membership__makerspace_id__in=ids)
    space = "membership__makerspace_id"
    lapsed = terms.filter(status="expired", next_term__isnull=True)
    return {
        "active_terms": count_by_space(terms.filter(status="active", ends_at__gt=now), space),
        "new_terms": count_by_space(in_window(terms.filter(kind="new"), "created_at", window), space),
        "renewals": count_by_space(in_window(terms.filter(kind="renewal"), "created_at", window), space),
        "lapsed": count_by_space(in_window(lapsed, "ends_at", window), space),
    }


MEMBERSHIP = Block(
    key="membership", label="Membership", switches=("membership",),
    gate=lambda space: module_enabled(space, "membership"),
    metrics=(
        Metric("active_terms", "Active memberships", timing="snapshot"),
        Metric("new_terms", "New memberships"),
        Metric("renewals", "Renewals"),
        Metric("lapsed", "Lapsed (not renewed)"),
    ),
    collect=_membership,
)
