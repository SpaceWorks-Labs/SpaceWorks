"""G/B call these from their existing authorized amendment surface."""
from django.utils.translation import gettext
import re
from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.audit.services import record
from apps.events import event_authority
from .admission_cohorts import roster_hash
from .admission_errors import check_version, fail
from .admission_ports import ports
from .admission_transactions import assert_locked, command, record as ctx_record
from .team_models import HackathonTeam, HackathonTeamException, HackathonTeamMember


def grant_exception_locked(*, team_id, actor, rule, member_id, reason_code, locks):
    assert_locked(locks, locks.event_id)
    team = get_object_or_404(HackathonTeam, pk=team_id, event_id=locks.event_id)
    event_authority.require(actor, team.event, "manage_hackathon")
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,39}", reason_code or ""):
        fail("reason_required", gettext("Select a reason for this exception."), status=400)
    members = list(team.memberships.filter(state="active"))
    if rule not in ("team_size", "attendance") or (rule == "team_size" and member_id is not None):
        fail("invalid_exception", gettext("Choose a specific supported rule."), status=400)
    if rule == "attendance" and member_id not in {m.member_id for m in members}:
        fail("not_found", gettext("Not found."), status=404)
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
            fail("reason_required", gettext("An active team and a reason are required."), status=400)
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
        from .team_notifications import emit_team_locked
        emit_team_locked(team=team, kind="team_reopened")
        return team


UNDO_WINDOW = timedelta(minutes=5)


def _staff_team(ctx, team_id):
    from .team_lifecycle import require_moderation
    require_moderation(ctx.event)
    return get_object_or_404(HackathonTeam.objects.select_for_update(), pk=team_id, event=ctx.event)


def rename(*, event_id, team_id, actor, data):
    """Organiser rename: bypasses the leader and the forming rule, never the unique-name rule."""
    from .team_workflow import normalized_name, require_available_name
    with command(event_id=event_id, actor=actor, data=data, action=f"teams.staff_rename:{team_id}", permission="manage_team") as ctx:
        team = _staff_team(ctx, team_id)
        if ctx.reference:
            return team
        check_version(team, data["expected_version"])
        if team.state == "disbanded":
            fail("not_found", gettext("Not found."), status=404)
        team.name, team.normalized_name = normalized_name(data["name"])
        require_available_name(ctx.event, team.normalized_name, team.pk)
        team.version += 1
        team.save()
        ctx_record(ctx, "team_renamed_by_staff", team, version=team.version)
        ctx.finish("team", team.pk)
        return team


def move_member(*, event_id, team_id, actor, data):
    """Move one active member to another open team of the same event; honours the max and any sealed cohort."""
    from .admission_cohorts import invalidate_locked
    from .team_lifecycle import elect_leader_locked
    with command(event_id=event_id, actor=actor, data=data, action=f"teams.staff_move:{team_id}", permission="manage_team") as ctx:
        source = _staff_team(ctx, team_id)
        if ctx.reference:
            return source
        check_version(source, data["expected_version"])
        if data["to_team_id"] == source.pk:
            fail("invalid_move", gettext("Choose a different team."), status=400)
        target = get_object_or_404(HackathonTeam.objects.select_for_update(), pk=data["to_team_id"], event=ctx.event)
        if source.state == "disbanded" or target.state != "forming":
            fail("team_locked", gettext("Both teams must be open."))
        row = get_object_or_404(HackathonTeamMember.objects.select_for_update(), team=source,
                                member_id=data["member_id"], state="active")
        if target.memberships.filter(state="active").count() >= ctx.config.team_max:
            fail("capacity_full", gettext("The team is at its maximum size."))
        invalidate_locked(ctx, source)
        invalidate_locked(ctx, target)
        row.team, row.joined_at = target, timezone.now()
        row.save()
        elect_leader_locked(source)
        target.version += 1
        target.save()
        ctx_record(ctx, "team_member_moved", row, from_team_id=source.pk, to_team_id=target.pk)
        from .team_notifications import emit_team_locked
        emit_team_locked(team=target, kind="team_membership_updated", member_ids=[row.member_id])
        ctx.finish("team", source.pk)
        return source


def delete(*, event_id, team_id, actor, data):
    """Soft delete with a five-minute undo: the roster is released and remembered in a snapshot."""
    from .admission_cohorts import invalidate_locked
    with command(event_id=event_id, actor=actor, data=data, action=f"teams.staff_delete:{team_id}", permission="manage_team") as ctx:
        team = _staff_team(ctx, team_id)
        if ctx.reference:
            return team
        check_version(team, data["expected_version"])
        if team.state == "disbanded":
            fail("not_found", gettext("Not found."), status=404)
        if ports().has_submission(team_id=team.pk):
            fail("active_submission", gettext("This team has a retained submission."))
        invalidate_locked(ctx, team)
        now = timezone.now()
        rows = list(team.memberships.select_for_update().filter(state="active").order_by("pk"))
        team.deleted_snapshot = {"leader_id": team.leader_id, "member_ids": [row.member_id for row in rows]}
        for row in rows:
            row.state, row.left_at = "removed", now
            row.save()
        for invite in team.invites.filter(revoked_at__isnull=True, redeemed_at__isnull=True):
            invite.revoked_at = now
            invite.save(update_fields=["revoked_at"])
        team.state, team.deleted_at, team.seeking_members, team.version = "disbanded", now, False, team.version + 1
        team.save()
        ctx_record(ctx, "team_deleted", team, version=team.version, members=len(rows))
        from .team_notifications import emit_team_locked
        emit_team_locked(team=team, kind="team_disbanded", member_ids=[row.member_id for row in rows])
        ctx.finish("team", team.pk)
        return team


def restore(*, event_id, team_id, actor, data):
    """Undo a delete inside the window; refuses if the name or any member has been taken meanwhile."""
    from .team_workflow import require_available_name
    with command(event_id=event_id, actor=actor, data=data, action=f"teams.staff_restore:{team_id}", permission="manage_team") as ctx:
        team = _staff_team(ctx, team_id)
        if ctx.reference:
            return team
        check_version(team, data["expected_version"])
        if team.deleted_at is None:
            fail("not_found", gettext("Not found."), status=404)
        if timezone.now() - team.deleted_at > UNDO_WINDOW:
            fail("undo_expired", gettext("The undo window has passed."))
        require_available_name(ctx.event, team.normalized_name, team.pk)
        member_ids = team.deleted_snapshot.get("member_ids", [])
        if HackathonTeamMember.objects.filter(event=ctx.event, member_id__in=member_ids, state="active").exists():
            fail("already_in_team", gettext("A member has joined another team since the delete."))
        rows = list(team.memberships.select_for_update().filter(state="removed", left_at=team.deleted_at))
        for row in rows:
            row.state, row.left_at = "active", None
            row.save()
        leader_id = team.deleted_snapshot.get("leader_id")
        team.leader_id = leader_id if leader_id in {row.member_id for row in rows} else (rows[0].member_id if rows else team.leader_id)
        team.state, team.deleted_at, team.deleted_snapshot, team.version = "forming", None, {}, team.version + 1
        team.save()
        ctx_record(ctx, "team_restored", team, version=team.version, members=len(rows))
        from .team_notifications import emit_team_locked
        emit_team_locked(team=team, kind="team_membership_updated", member_ids=[row.member_id for row in rows])
        ctx.finish("team", team.pk)
        return team
