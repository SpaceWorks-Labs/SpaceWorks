"""Which events a person may say a machine job or session was "for" (decision 342).

Always available (no switch): the picker lists the events in THIS makerspace the person may act for, as
a registered participant (or crew place), an active hackathon team member, approved crew, an organiser, or
event staff (event authority, including a Space Manager's tenant-wide authority). Cancelled and completed
events are never offered. One space only: an event of another makerspace is never eligible.
"""
from django.db.models import Q

from . import event_authority, event_permissions
from .contributions.models_crew import EventCrewMember
from .hackathons.team_models import HackathonTeamMember
from .models import Event, EventRegistration

CLOSED = (Event.Status.CANCELLED, Event.Status.COMPLETED)


def linkable_events(makerspace):
    """Events in `makerspace` a link may point at, regardless of person."""
    from apps.makerspaces.platform import module_enabled
    if not module_enabled(makerspace, "events"):
        return Event.objects.none()
    return Event.objects.filter(makerspace=makerspace).exclude(status__in=CLOSED)


def eligible_events(user, makerspace):
    """Linkable events this person may act for, soonest first."""
    base = linkable_events(makerspace)
    if user is None or not getattr(user, "pk", None):
        return base.none()
    registered = EventRegistration.objects.filter(
        member=user, status__in=(EventRegistration.Status.REGISTERED, EventRegistration.Status.ATTENDED))
    teams = HackathonTeamMember.objects.filter(member=user, state="active")
    crew = EventCrewMember.objects.filter(member=user, state="approved")
    staff = event_authority.events_for(user, event_permissions.VIEW, base)
    return base.filter(
        Q(pk__in=registered.values("event_id")) | Q(pk__in=teams.values("event_id"))
        | Q(pk__in=crew.values("event_id")) | Q(pk__in=staff.values("pk"))
    ).order_by("starts_at", "id")
