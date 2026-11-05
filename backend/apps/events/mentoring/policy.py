"""Live mentor eligibility. Display role labels and cached permission unions never suffice."""
from datetime import datetime
from django.apps import apps
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.events import event_authority
from apps.events.contributions.commands import active_member
from apps.events.contributions.errors import ProgrammeError
from apps.events.contributions.models_roles import EventRoleAssignment
from apps.events.contributions.ports import ports
from .models_queue import MentorProfile, MentorTeamAssignment
from .models_rounds import MentorConflict


def in_windows(windows, at):
    for window in windows:
        start = datetime.fromisoformat(window["starts_at"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(window["ends_at"].replace("Z", "+00:00"))
        if start.tzinfo is not None and end.tzinfo is not None and start <= at < end:
            return True
    return False


def covers_interval(windows, start, end):
    return any(datetime.fromisoformat(row["starts_at"].replace("Z", "+00:00")) <= start
        and end <= datetime.fromisoformat(row["ends_at"].replace("Z", "+00:00")) for row in windows)


def mentor_for(actor, event, *, at=None, assignment_id=None, on_shift=True):
    active_member(actor)
    rows = EventRoleAssignment.objects.filter(event=event, member=actor,
        role="mentor", state="approved", imported_inert=False)
    assignment = get_object_or_404(rows, **({"pk": assignment_id} if assignment_id else {}))
    event_authority.require(actor, event, "mentor_queue")
    profile = get_object_or_404(MentorProfile, assignment=assignment, event=event)
    if on_shift and not in_windows(profile.availability or assignment.availability, at or timezone.now()):
        raise ProgrammeError("mentor_off_shift", "You are outside your mentoring availability.", status=403)
    return assignment, profile


def visit_eligible(*, assignment, profile, team_id, skill_tags=(), at=None, priority_until=None):
    now = at or timezone.now()
    ports().teams.require_eligible(event_id=assignment.event_id, team_id=team_id, at=now)
    members = ports().teams.member_ids(event_id=assignment.event_id, team_id=team_id)
    if assignment.member_id in members or MentorConflict.objects.filter(mentor=assignment,
        team_id=team_id, active=True, kind__in=["declared", "affiliation"]).exists():
        return False
    assigned = MentorTeamAssignment.objects.filter(event_id=assignment.event_id,
        mentor_assignment=assignment, team_id=team_id, state="active",
        active_from__lte=now, ended_at__isnull=True).exists()
    if assigned:
        return True
    has_assigned = MentorTeamAssignment.objects.filter(event_id=assignment.event_id,
        team_id=team_id, state="active", active_from__lte=now, ended_at__isnull=True).exists()
    if has_assigned and priority_until and now < priority_until:
        return False
    return not skill_tags or bool(set(profile.skills) & set(skill_tags))


def queue_manager(actor, event):
    return event_authority.can(actor, event, "manage_team") and event_authority.can(actor, event, "mentor_queue")


def require_queue_manager(actor, event):
    if not queue_manager(actor, event):
        raise ProgrammeError("queue_management_required", "Queue management is required.", status=403)


def is_conflicted(*, member_id, team_id, round_id=None):
    """C conflict provider for D. A round override cannot weaken this predicate."""
    team = get_object_or_404(apps.get_model("events", "HackathonTeam"), pk=team_id)
    if member_id in ports().teams.member_ids(event_id=team.event_id, team_id=team_id):
        return True
    roles = EventRoleAssignment.objects.filter(event_id=team.event_id, member_id=member_id, role="mentor")
    return MentorConflict.objects.filter(mentor__in=roles, team_id=team_id, active=True).exists() or (
        MentorTeamAssignment.objects.filter(mentor_assignment__in=roles, team_id=team_id,
                                            state__in=["active", "ended"]).exists())


def drop_in_allowed(event):
    """Mentor help without a team (#128 C-36, E2-f): any event that is not a team hackathon.

    A hackathon here is what the programme context calls one: an enabled `HackathonConfig`
    while `events.hackathons` is on. Hackathons keep their team-only queue unchanged.
    """
    from apps.events.hackathons.admission_feature import hackathon_enabled
    from apps.events.hackathons.admission_models import HackathonConfig
    return not (hackathon_enabled(event.makerspace) and HackathonConfig.objects.filter(event=event, enabled=True).exists())


def request_eligible(*, assignment, profile, row, **kwargs):
    """`visit_eligible` for a team request; a drop-in only refuses the requester themself."""
    if row.team_id is None:
        if assignment.member_id == row.raised_by_id:
            return False
        tags = kwargs.get("skill_tags") or ()
        return not tags or bool(set(profile.skills) & set(tags))
    return visit_eligible(assignment=assignment, profile=profile, team_id=row.team_id, **kwargs)


def request_alias(row, event):
    """What mentors see for the asker: the team's alias, or a drop-in's first name only."""
    if row.team_id is not None:
        return ports().teams.alias(event_id=event.pk, team_id=row.team_id)
    user = row.raised_by
    first = ((getattr(user, "first_name", "") or getattr(user, "display_name", "") or "").split(" ") or [""])[0]
    return f"{first or 'Attendee'} (drop-in)"
