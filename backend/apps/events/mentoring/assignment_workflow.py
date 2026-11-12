"""Deterministic load-balanced assignment; preview never writes grants or mappings."""
from django.utils.translation import gettext
from dataclasses import dataclass
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.events.contributions import commands
from apps.events.contributions.errors import ProgrammeError
from apps.events.contributions.models_roles import EventRoleAssignment
from apps.events.contributions.ports import ports
from .models_queue import MentorProfile, MentorTeamAssignment
from .models_rounds import MentorConflict
from . import policy
from .models_operations import MentorAssignmentRun
from apps.events.contributions.errors import check_version, require_state


@dataclass(frozen=True)
class Candidate:
    id: int
    skills: frozenset[str]
    load: int
    capacity: int
    excluded_teams: frozenset[int]


def allocate(*, teams, candidates, mode, skill_weights=None, manual=None):
    if mode not in ("manual", "round_robin", "skill_match"):
        raise ProgrammeError("invalid_mode", gettext("Choose a supported assignment mode."), status=400)
    weights = skill_weights or {}
    loads = {c.id: c.load for c in candidates}
    decisions, unsatisfied = [], []
    for team_id, skills in sorted(teams.items()):
        eligible = [c for c in candidates if team_id not in c.excluded_teams and loads[c.id] < c.capacity]
        if mode == "manual":
            eligible = [c for c in eligible if c.id == (manual or {}).get(team_id)]
        if not eligible:
            unsatisfied.append(team_id)
            continue
        def order(candidate):
            score = sum(weights.get(tag, 1) for tag in set(skills) & candidate.skills) if mode == "skill_match" else 0
            return (-score, loads[candidate.id], candidate.id)
        winner = min(eligible, key=order)
        decisions.append({"team_id": team_id, "mentor_assignment_id": winner.id})
        loads[winner.id] += 1
    return {"assignments": decisions, "unsatisfied_team_ids": unsatisfied}


def preview(*, actor, event, payload, locked_accounts=None):
    from apps.events import event_authority
    from apps.makerspaces.guards import require_feature
    event_authority.require(actor, event, "manage_team")
    require_feature(event.makerspace, "events.mentoring")
    team_ids = payload["team_ids"]
    candidates = []
    roles = EventRoleAssignment.objects.filter(event=event, role="mentor", state="approved", imported_inert=False)
    for role in roles.select_related("member").order_by("pk"):
        if locked_accounts is not None and role.member_id not in locked_accounts:
            raise ProgrammeError("scope_changed", gettext("The mentor roster changed; refresh the preview."))
        if not MentorProfile.objects.filter(assignment=role).exists():
            continue
        try:
            _, profile = policy.mentor_for(role.member, event, assignment_id=role.pk)
        except ProgrammeError as exc:
            if exc.status_code in (403, 404):
                continue
            raise
        excluded = set(MentorConflict.objects.filter(mentor=role, active=True,
            kind__in=["declared", "affiliation"]).values_list("team_id", flat=True))
        for team_id in team_ids:
            if role.member_id in ports().teams.member_ids(event_id=event.pk, team_id=team_id):
                excluded.add(team_id)
        active = MentorTeamAssignment.objects.filter(mentor_assignment=role, ended_at__isnull=True)
        excluded.update(active.values_list("team_id", flat=True))
        candidates.append(Candidate(role.pk, frozenset(profile.skills), active.count(),
                                    profile.max_active_teams, frozenset(excluded)))
    teams = {}
    for team_id in team_ids:
        ports().teams.require_eligible(event_id=event.pk, team_id=team_id, at=timezone.now())
        ports().teams.require_practice(event_id=event.pk, team_id=team_id, practice_run_id=None)
        teams[team_id] = ports().teams.skills(event_id=event.pk, team_id=team_id)
    return allocate(teams=teams, candidates=candidates, mode=payload["mode"],
        skill_weights=payload.get("skill_weights"),
        manual={item["team_id"]: item["mentor_assignment_id"] for item in payload.get("manual", [])})


def assign(*, actor, event_id, payload, proposed=False):
    mentors = tuple(EventRoleAssignment.objects.filter(event_id=event_id, role="mentor",
        state="approved", imported_inert=False).values_list("member_id", flat=True))
    def mutate(event, locks):
        if payload["expected_version"] != getattr(event, "version", 1):
            raise ProgrammeError("stale_version", gettext("The event changed; refresh the assignment preview."))
        result = preview(actor=actor, event=event, payload=payload, locked_accounts=locks.account_ids)
        rows = []
        for item in result["assignments"]:
            rows.append(commands.new_row(MentorTeamAssignment, event, **item, mode=payload["mode"],
                state="proposed" if proposed else "active", active_from=timezone.now(), created_by=actor, run_id=payload["operation_id"]))
        return commands.new_row(MentorAssignmentRun, event, run_id=payload["operation_id"],
            mode=payload["mode"], decisions=[{**item, "id": row.pk, "version": row.version,
                "state": row.state} for item, row in zip(result["assignments"], rows)],
            unsatisfied_team_ids=result["unsatisfied_team_ids"], created_by=actor)

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action="mentor.propose" if proposed else "mentor.assign", feature="events.mentoring", permission="manage_team", mutate=mutate,
        account_ids=mentors, authority_ids=mentors, status=201)


def transition(*, actor, event_id, assignment_id, payload, action):
    initial = get_object_or_404(MentorTeamAssignment, pk=assignment_id, event_id=event_id)
    def mutate(event, locks):
        row = get_object_or_404(MentorTeamAssignment.objects.select_for_update(), pk=assignment_id, event=event)
        check_version(row, payload["expected_version"])
        if action == "activate":
            require_state(row, "proposed")
            mentor, profile = policy.mentor_for(row.mentor_assignment.member, event,
                assignment_id=row.mentor_assignment_id)
            if not policy.visit_eligible(assignment=mentor, profile=profile, team_id=row.team_id):
                raise ProgrammeError("mentor_conflict", gettext("Choose an eligible mentor."), status=403)
            count = MentorTeamAssignment.objects.filter(mentor_assignment=mentor,
                ended_at__isnull=True).exclude(pk=row.pk).count()
            if count >= profile.max_active_teams:
                raise ProgrammeError("mentor_full", gettext("This mentor is at capacity."))
            return commands.changed(row, state="active", active_from=timezone.now())
        if action != "end":
            raise ProgrammeError("invalid_transition", gettext("Unknown assignment command."), status=400)
        require_state(row, "proposed", "active")
        return commands.changed(row, state="ended", ended_at=timezone.now())

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action=f"mentor.assignment.{action}", feature="events.mentoring", permission="manage_team", mutate=mutate,
        account_ids=(initial.mentor_assignment.member_id,), authority_ids=(initial.mentor_assignment.member_id,))


def end_role_locked(*, assignment, actor, event):
    from apps.audit.services import record
    from .models_queue import EventHelpRequest
    from .help_expiry import release_locked
    for row in MentorTeamAssignment.objects.select_for_update().filter(mentor_assignment=assignment,
            ended_at__isnull=True).order_by("pk"):
        commands.changed(row, state="ended", ended_at=timezone.now())
        record(actor, "event.mentor.assignment.ended_with_role", makerspace=event.makerspace, target=row)
    for row in EventHelpRequest.objects.select_for_update().filter(claimed_by=assignment,
            state="claimed").order_by("pk"):
        release_locked(row=row, event=event, actor=actor, kind="role_ended")


def run_projection(row):
    from apps.events.contributions.api_common import envelope
    return {**envelope(row), "state": "completed", "run_id": row.run_id,
        "assignments": row.decisions, "unsatisfied_team_ids": row.unsatisfied_team_ids}


def mapping_projection(row):
    from apps.events.contributions.api_common import envelope
    return {**envelope(row), **{key: getattr(row, key) for key in (
        "mentor_assignment_id", "team_id", "mode", "active_from", "ended_at", "run_id")}}
