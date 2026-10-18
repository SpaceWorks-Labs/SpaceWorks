"""Only writer of team and membership state; event parent serializes slots."""
import unicodedata
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .admission_errors import check_version, fail
from .admission_models import HackathonApplication
from .admission_transactions import assert_locked, command, notice, record
from .team_models import HackathonTeam, HackathonTeamMember


def normalized_name(name):
    value = " ".join(unicodedata.normalize("NFKC", name).split())
    if not value or len(value) > 100 or any(unicodedata.category(c).startswith("C") for c in value):
        fail("invalid_team_name", "Use a team name of 1–100 printable characters.", status=400)
    return value, value.casefold()


def require_forming(config, team, *, at=None):
    now = at or timezone.now()
    reopened = getattr(team, "roster_reopened_until", None)
    if team.state != "forming" or (config.team_lock_at and now >= config.team_lock_at and not (reopened and now < reopened)):
        fail("team_locked", "The team roster is locked.")


def require_leader(team, actor):
    if team.leader_id != actor.pk:
        fail("leader_required", "Only the team leader can do this.", status=403)


def member_application(ctx, actor):
    app = HackathonApplication.objects.filter(event=ctx.event, member=actor).first()
    if ctx.config.team_mode == "team_together":
        if app is None:
            app = HackathonApplication.objects.create(event=ctx.event, member=actor)
            record(ctx, "application_saved", app, version=app.version)
        if app.state not in ("draft", "submitted"):
            fail("team_ineligible", "This application cannot join a forming cohort.")
    else:
        states = ("confirmed", "offered") if ctx.config.team_eligibility == "offered" else ("confirmed",)
        if app is None or app.state not in states:
            fail("team_ineligible", "Confirm your place before joining a team.")
    return app


def activate_locked(ctx, team, member, application):
    require_forming(ctx.config, team)
    if HackathonTeamMember.objects.filter(event=ctx.event, member=member, state="active").exists():
        fail("already_in_team", "You already belong to a team for this event.")
    if team.memberships.filter(state="active").count() >= ctx.config.team_max:
        fail("capacity_full", "The team's last place was taken.")
    from .admission_cohorts import invalidate_locked
    invalidate_locked(ctx, team)
    row = team.memberships.filter(member=member, state__in=("requested", "invited")).first()
    row = row or HackathonTeamMember(event=ctx.event, team=team, member=member, application=application, creator=ctx.actor)
    row.state, row.joined_at = "active", timezone.now()
    row.save()
    team.version += 1
    team.save()
    record(ctx, "team_member_joined", row, team_id=team.pk, version=team.version)
    return row


def create(*, event_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action="teams.create", owner=True) as ctx:
        if ctx.reference:
            return get_object_or_404(HackathonTeam, pk=ctx.reference["id"], event=ctx.event)
        check_version(None, data["expected_version"])
        if ctx.config.team_mode == "solo":
            fail("solo_team_automatic", "Your solo team is created when you confirm your place.")
        app = member_application(ctx, actor)
        name, key = normalized_name(data.get("name", ""))
        require_available_name(ctx.event, key)
        team = HackathonTeam.objects.create(event=ctx.event, leader=actor, name=name, normalized_name=key,
            seeking_members=data.get("seeking_members", False), finder_intro=data.get("finder_intro", ""), skills=data.get("skills", []))
        activate_locked(ctx, team, actor, app)
        record(ctx, "team_created", team, version=team.version)
        ctx.finish("team", team.pk, status=201)
        return team


def require_available_name(event, key, exclude=None):
    if HackathonTeam.objects.filter(event=event, normalized_name=key).exclude(state="disbanded").exclude(pk=exclude).exists():
        suggestions = []
        for number in range(2, 102):
            candidate = key[:94] + f" {number}"
            if not HackathonTeam.objects.filter(event=event, normalized_name=candidate).exclude(state="disbanded").exists():
                suggestions.append(candidate)
            if len(suggestions) == 3:
                break
        fail("team_name_taken", "That team name is in use.", fields={"name": suggestions})


def update(*, event_id, team_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action=f"teams.edit:{team_id}", owner=True) as ctx:
        team = get_object_or_404(HackathonTeam.objects.select_for_update(), event=ctx.event, pk=team_id)
        require_leader(team, actor)
        if ctx.reference:
            return team
        check_version(team, data["expected_version"])
        require_forming(ctx.config, team)
        if "name" in data:
            team.name, team.normalized_name = normalized_name(data["name"])
            require_available_name(ctx.event, team.normalized_name, team.pk)
        for key in ("seeking_members", "finder_intro", "skills"):
            if key in data:
                setattr(team, key, data[key])
        team.version += 1
        team.save()
        record(ctx, "team_updated", team, version=team.version)
        ctx.finish("team", team.pk)
        return team


def create_solo_locked(ctx, application):
    existing = HackathonTeamMember.objects.filter(event=ctx.event, member_id=application.member_id, state="active").first()
    if existing:
        return existing.team
    name = f"Solo {application.pk}"
    team = HackathonTeam.objects.create(event=ctx.event, leader_id=application.member_id, name=name, normalized_name=name.casefold())
    HackathonTeamMember.objects.create(event=ctx.event, team=team, application=application,
        member_id=application.member_id, creator=ctx.actor, state="active", joined_at=timezone.now())
    record(ctx, "solo_team_created", team, application_id=application.pk)
    return team


def lock_roster_locked(*, team_id, locks):
    assert_locked(locks, locks.event_id)
    team = get_object_or_404(HackathonTeam.objects.select_for_update(), pk=team_id, event_id=locks.event_id)
    from .admission_workflow import require_team_eligible
    require_team_eligible(team_id=team_id, event_id=locks.event_id, at=timezone.now())
    from .admission_cohorts import roster_hash
    members = list(team.memberships.filter(state="active"))
    digest = roster_hash(members)
    if team.state == "locked":
        if team.roster_hash != digest:
            fail("roster_changed", "The sealed roster no longer matches.")
        return digest
    team.state, team.roster_hash, team.locked_at = "locked", digest, timezone.now()
    team.seeking_members, team.version = False, team.version + 1
    team.save()
    from apps.audit.services import record as audit_record
    audit_record(None, "event.hackathon.team_locked", makerspace=team.event.makerspace,
                 target=team, meta={"version": team.version, "roster_hash": digest})
    return digest
