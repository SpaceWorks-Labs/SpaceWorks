"""G/B call these from their existing authorized amendment surface."""
import re
from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.audit.services import record
from apps.events import event_authority
from .admission_cohorts import roster_hash
from .admission_errors import check_version, fail
from .admission_ports import ports
from .admission_transactions import assert_locked, command
from .team_models import HackathonTeam, HackathonTeamException


def grant_exception_locked(*, team_id, actor, rule, member_id, reason_code, locks):
    assert_locked(locks, locks.event_id)
    team = get_object_or_404(HackathonTeam, pk=team_id, event_id=locks.event_id)
    event_authority.require(actor, team.event, "manage_hackathon")
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,39}", reason_code or ""):
        fail("reason_required", "Select a reason for this exception.", status=400)
    members = list(team.memberships.filter(state="active"))
    if rule not in ("team_size", "attendance") or (rule == "team_size" and member_id is not None):
        fail("invalid_exception", "Choose a specific supported rule.", status=400)
    if rule == "attendance" and member_id not in {m.member_id for m in members}:
        fail("not_found", "Not found.", status=404)
    row = HackathonTeamException.objects.create(team=team, rule=rule, member_id=member_id,
        roster_hash=roster_hash(members), reason_code=reason_code, approved_by=actor, valid_until=team.event.ends_at)
    record(actor, "event.hackathon.team_exception_granted", makerspace=team.event.makerspace,
           target=row, meta={"team_id": team.pk, "rule": rule, "member_id": member_id, "reason_code": reason_code})
    return row.pk


def reopen(*, event_id, team_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action=f"teams.reopen:{team_id}", permission="manage_hackathon") as ctx:
        team = get_object_or_404(HackathonTeam.objects.select_for_update(), pk=team_id, event=ctx.event)
        if ctx.reference:
            return team
        check_version(team, data["expected_version"])
        if team.state == "disbanded" or not re.fullmatch(r"[a-z][a-z0-9_]{2,39}", data.get("reason_code", "")):
            fail("reason_required", "An active team and a reason are required.", status=400)
        ports().reopen_submission_locked(team_id=team.pk, actor_id=actor.pk, reason_code=data["reason_code"], locks=ctx.locks)
        cohort = getattr(team, "cohort", None)
        if cohort and cohort.state in ("submitted", "offered", "confirmed", "waitlisted"):
            from .admission_cohorts import reopen_locked
            reopen_locked(ctx, cohort)
        team.state, team.eligibility_issue = "forming", False
        team.roster_reopened_until = min(ctx.event.ends_at, timezone.now() + timedelta(hours=1))
        team.roster_hash, team.locked_at, team.version = "", None, team.version + 1
        team.save()
        record(actor, "event.hackathon.team_reopened", makerspace=ctx.event.makerspace,
               target=team, meta={"version": team.version, "reason_code": data["reason_code"]})
        ctx.finish("team", team.pk)
        return team
