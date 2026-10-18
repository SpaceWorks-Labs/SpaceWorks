"""Leaving, disbanding and eligibility repair preserve frozen roster history."""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .admission_errors import check_version, fail
from .admission_ports import ports
from .admission_transactions import command, record, notice
from .team_models import HackathonTeam, HackathonTeamMember
from .team_workflow import require_forming, require_leader


def elect_leader_locked(team):
    survivor = team.memberships.filter(state="active").order_by("joined_at", "pk").first()
    if survivor:
        team.leader_id = survivor.member_id
    else:
        team.state, team.seeking_members = "disbanded", False
    team.version += 1
    team.save()


def eligibility_changed_locked(ctx, application):
    from .team_models import HackathonFinderProfile
    finder = HackathonFinderProfile.objects.filter(event=ctx.event, member_id=application.member_id, opted_in=True).first()
    if finder and application.state not in ("offered", "confirmed"):
        finder.opted_in, finder.version = False, finder.version + 1
        finder.save()
        record(ctx, "finder_updated", finder, opted_in=False, version=finder.version)
    if application.state not in ("rejected", "declined", "expired", "withdrawn"):
        return
    membership = HackathonTeamMember.objects.filter(event=ctx.event, application=application, state="active").first()
    if membership is None:
        return
    team = HackathonTeam.objects.select_for_update().get(pk=membership.team_id)
    if team.state == "locked" or (ctx.config.team_lock_at and timezone.now() >= ctx.config.team_lock_at):
        team.eligibility_issue, team.version = True, team.version + 1
        team.save()
        record(ctx, "team_eligibility_flagged", team, application_id=application.pk)
    else:
        membership.state, membership.left_at = "removed", timezone.now()
        membership.save()
        elect_leader_locked(team)
        # An ended offer retains its sealed evidence. A later explicit reopen
        # invalidates that seal; membership edits never rewrite an accepted roster.
        record(ctx, "team_member_removed", membership, team_id=team.pk)
    for peer in team.memberships.filter(state="active").select_related("application"):
        notice(ctx, peer.application, "team_eligibility_changed")


def leave(*, event_id, team_id, actor, data, cancel=False):
    with command(event_id=event_id, actor=actor, data=data, action=f"teams.{'cancel' if cancel else 'leave'}:{team_id}", owner=True) as ctx:
        team = get_object_or_404(HackathonTeam.objects.select_for_update(), pk=team_id, event=ctx.event)
        member = get_object_or_404(HackathonTeamMember, team=team, member=actor, state="active")
        if cancel:
            require_leader(team, actor)
        if ctx.reference:
            return team
        check_version(team, data["expected_version"])
        require_forming(ctx.config, team)
        if ports().has_submission(team_id=team.pk):
            fail("active_submission", "This team has a retained submission.")
        from .admission_cohorts import invalidate_locked
        invalidate_locked(ctx, team)
        selected = list(team.memberships.select_for_update().filter(state="active").order_by("pk")) if cancel else [member]
        for row in selected:
            row.state, row.left_at = "left", timezone.now()
            row.save()
            record(ctx, "team_member_left", row, team_id=team.pk)
        elect_leader_locked(team)
        if team.state == "disbanded":
            for invite in team.invites.filter(revoked_at__isnull=True, redeemed_at__isnull=True):
                invite.revoked_at = timezone.now()
                invite.save(update_fields=["revoked_at"])
            record(ctx, "team_disbanded", team, reason_code=data.get("reason_code", "empty_team"))
        ctx.finish("team", team.pk)
        return team


def lock(*, event_id, team_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action=f"teams.lock:{team_id}", owner=True) as ctx:
        team = get_object_or_404(HackathonTeam.objects.select_for_update(), event=ctx.event, pk=team_id)
        require_leader(team, actor)
        if ctx.reference:
            return team
        check_version(team, data["expected_version"])
        cohort = getattr(team, "cohort", None)
        if ctx.config.team_mode == "team_together" and (cohort is None or cohort.state == "draft"):
            from .admission_cohorts import seal_locked
            seal_locked(ctx, team)
            team.version += 1
            team.save()
        else:
            from .team_workflow import lock_roster_locked
            lock_roster_locked(team_id=team.pk, locks=ctx.locks)
            team.refresh_from_db()
        ctx.finish("team", team.pk)
        return team
