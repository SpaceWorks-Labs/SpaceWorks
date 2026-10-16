"""Counts-only plug-in contract. Sources return owned, publishable milestones.

Register at AppConfig.ready(), without queries. No source runs unless the graph,
its family's consent and its module are enabled. Corrections are query-derived.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable

FAMILY_CONSENTS = {
    "events": "show_events", "speaking": "show_speaking", "projects": "show_projects",
    "machine_jobs": "show_machine_activity", "bookings": "show_bookings", "loans": "show_loans",
}


@dataclass(frozen=True)
class ActivityMilestone:
    record: str
    occurred_at: datetime


@dataclass(frozen=True)
class ActivitySource:
    family: str
    module: str
    milestones: Callable[[object, datetime, datetime], Iterable[ActivityMilestone]]


_sources = {}


def register_activity_source(source):
    if source.family not in FAMILY_CONSENTS:
        raise ValueError("Unknown public activity family")
    if source.family in _sources and _sources[source.family] != source:
        raise RuntimeError(f"Duplicate activity source: {source.family}")
    _sources[source.family] = source


def activity_sources():
    return tuple(_sources.values())


def projects(profile, start, end):
    from django.db.models import Q
    for row in profile.projects.filter(public_visible=True).filter(
        Q(created_at__gte=start, created_at__lt=end) | Q(updated_at__gte=start, updated_at__lt=end)
    ).only("pk", "created_at", "updated_at"):
        # Created + updated on the same local day count once for this project.
        for moment in (row.created_at, row.updated_at):
            yield ActivityMilestone(str(row.pk), moment)


def register_builtin_sources():
    register_activity_source(ActivitySource("projects", "membership", projects))
    register_activity_source(ActivitySource("events", "events", events))
    register_activity_source(ActivitySource("machine_jobs", "machine_service", machine_jobs))


def attended_registrations(profile):
    from apps.events.member_history import registrations_for_space
    from apps.events.models import Event, EventRegistration
    return registrations_for_space(profile.membership.makerspace, profile.membership.user).filter(
        status=EventRegistration.Status.ATTENDED, event__is_public=True,
        event__status__in=[Event.Status.PUBLISHED, Event.Status.COMPLETED],
        check_in_events__source__in=["online", "qr", "venue_station", "offline_sync"],
    ).distinct()


def events(profile, start, end):
    # Only current ATTENDED state counts; historical check-ins cannot resurrect an
    # undone attendance. One event per person, even with repeated scans/tickets.
    from apps.events.models import EventCheckInEvent
    from django.db.models import Min
    allowed = attended_registrations(profile).values_list("pk", flat=True)
    rows = EventCheckInEvent.objects.filter(
        registration_id__in=allowed,
        source__in=["online", "qr", "venue_station", "offline_sync"],
    ).values("event_id").annotate(moment=Min("attended_at")).filter(
        moment__gte=start, moment__lt=end,
    ).values_list("event_id", "moment")
    for event_id, moment in rows:
        yield ActivityMilestone(str(event_id), moment)


def machine_jobs(profile, start, end):
    from apps.machines.models import MachineServiceRequest
    for pk, moment in MachineServiceRequest.objects.filter(
        makerspace=profile.membership.makerspace, member=profile.membership.user,
        status__in=["completed", "collected"], completed_at__gte=start, completed_at__lt=end,
    ).values_list("pk", "completed_at"):
        yield ActivityMilestone(str(pk), moment)
