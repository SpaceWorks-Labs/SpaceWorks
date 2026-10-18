"""Deterministic load-balanced assignment; preview never writes grants or mappings."""
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


@dataclass(frozen=True)
class Candidate:
    id: int
    skills: frozenset[str]
    load: int
    capacity: int
    excluded_teams: frozenset[int]


def allocate(*, teams, candidates, mode, skill_weights=None, manual=None):
    if mode not in ("manual", "round_robin", "skill_match"):
        raise ProgrammeError("invalid_mode", "Choose a supported assignment mode.", status=400)
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


def preview(*, actor, event, payload):
    from apps.events import event_authority
    from apps.makerspaces.guards import require_feature
    event_authority.require(actor, event, "manage_team")
    require_feature(event.makerspace, "events.mentoring")
    team_ids = payload["team_ids"]
    candidates = []
    roles = EventRoleAssignment.objects.filter(event=event, role="mentor", state="approved", imported_inert=False)
    for role in roles.select_related("member").order_by("pk"):
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


def assign(*, actor, event_id, payload):
    def mutate(event, locks):
        if payload["expected_version"] != getattr(event, "version", 1):
            raise ProgrammeError("stale_version", "The event changed; refresh the assignment preview.")
        result = preview(actor=actor, event=event, payload=payload)
        rows = []
        for item in result["assignments"]:
            rows.append(commands.new_row(MentorTeamAssignment, event, **item, mode=payload["mode"],
                active_from=timezone.now(), created_by=actor, run_id=payload["operation_id"]))
        if not rows:
            raise ProgrammeError("insufficient_coverage", "No eligible mentors can cover these teams.", **result)
        return rows[0]

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action="mentor.assign", feature="events.mentoring", permission="manage_team", mutate=mutate, status=201)
