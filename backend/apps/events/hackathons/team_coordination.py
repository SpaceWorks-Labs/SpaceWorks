"""Private append-only comments and explicit finder opt-in."""
from django.shortcuts import get_object_or_404
from .admission_errors import check_version, fail
from .admission_transactions import command, record
from .team_models import HackathonFinderProfile, HackathonTeam, TeamComment
from .team_projection import require_own_team
from .team_workflow import member_application


def comment(*, event_id, team_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action=f"teams.comment:{team_id}", owner=True) as ctx:
        team = require_own_team(event_id=event_id, team_id=team_id, actor=actor)
        if ctx.reference:
            return get_object_or_404(TeamComment, pk=ctx.reference["id"], team=team)
        check_version(team, data["expected_version"])
        if team.state == "disbanded":
            fail("team_closed", "This team is closed.")
        row = TeamComment.objects.create(team=team, author=actor, encrypted_body=data["body"])
        team.version += 1
        team.save()
        record(ctx, "team_comment_added", row, team_id=team.pk, version=team.version)
        ctx.finish("team_comment", row.pk, status=201)
        return row


def project_comment(row):
    return {"id": row.pk, "team_id": row.team_id, "body": row.encrypted_body,
            "created_at": row.created_at, "team_version": row.team.version}


def finder_profile(*, event_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action="finder.edit", owner=True) as ctx:
        if not ctx.config.finder_enabled or ctx.config.team_mode != "individual_then_team":
            fail("not_found", "Not found.", status=404)
        if data.get("opted_in") is not False:
            member_application(ctx, actor)
        row = HackathonFinderProfile.objects.select_for_update().filter(event=ctx.event, member=actor).first()
        if ctx.reference:
            return row
        check_version(row, data["expected_version"])
        row = row or HackathonFinderProfile(event=ctx.event, member=actor, version=0)
        for key in ("opted_in", "intro", "skills"):
            if key in data:
                setattr(row, key, data[key])
        row.version += 1
        row.save()
        record(ctx, "finder_updated", row, opted_in=row.opted_in, version=row.version)
        ctx.finish("finder_profile", row.pk)
        return row


def project_finder_profile(row, *, event_id):
    return {"id": row.pk if row else None, "event_id": event_id, "version": row.version if row else 0,
            "state": "visible" if row and row.opted_in else "hidden", "allowed_actions": ["edit"],
            "opted_in": bool(row and row.opted_in), "intro": row.intro if row else "", "skills": row.skills if row else []}
