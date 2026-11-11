"""Explicit minimal roster/finder shapes; no account/contact/answer serializer."""
from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from .admission_errors import fail
from .admission_ports import ports
from .team_models import HackathonTeam


def require_own_team(*, event_id, team_id, actor):
    return get_object_or_404(HackathonTeam.objects.filter(event_id=event_id, memberships__member=actor,
                                                        memberships__state="active"), pk=team_id)


def profile(event_id, member_id):
    value = ports().public_profile(event_id=event_id, member_id=member_id, scope="team")
    if value is None:
        return None
    # E owns live selected membership/photo/consent checks. No private fallback.
    return {key: value[key] for key in ("display_name", "url", "photo_url") if key in value}


def moderation_actions(team, *, leader, forming):
    """E-F4: which `events.team_moderation` commands the screen may offer (the routes re-check everything)."""
    from apps.makerspaces.platform import feature_enabled
    from .team_lifecycle import MODERATION
    if team.state == "disbanded" or not feature_enabled(team.event.makerspace, MODERATION):
        return []
    return (["handover"] if leader else []) + (["remove_member"] if leader and forming else []) \
        + (["cancel_registration"] if forming else [])


def project_team(team, *, actor, config, finder=False):
    members = list(team.memberships.filter(state="active").order_by("joined_at", "pk"))
    if finder:
        return {"id": team.pk, "event_id": team.event_id, "version": team.version,
                "kind": "team", "name": team.name, "skills": team.skills, "intro": team.finder_intro,
                "slots": max(0, config.team_max - len(members)),
                "profiles": [p for member in members if (p := profile(team.event_id, member.member_id)) is not None]}
    if actor.pk not in {m.member_id for m in members}:
        fail("not_found", gettext("Not found."), status=404)
    leader = team.leader_id == actor.pk
    actions = []
    if team.state == "forming":
        actions = ["leave", "comment"] + (["edit", "invite", "accept", "decline", "lock", "cancel"] if leader else [])
    actions += moderation_actions(team, leader=leader, forming="leave" in actions)
    return {"id": team.pk, "event_id": team.event_id, "version": team.version,
            "state": team.state, "name": team.name, "allowed_actions": actions,
            "leader_member_id": team.leader_id, "team_mode": config.team_mode,
            "seeking_members": team.seeking_members, "finder_intro": team.finder_intro, "skills": team.skills,
            "eligibility_issue": team.eligibility_issue, "roster_hash": team.roster_hash,
            "members": [{"id": member.pk, "member_id": member.member_id,
                         "joined_at": member.joined_at, "profile": profile(team.event_id, member.member_id)} for member in members],
            "join_requests": [{"id": member.pk, "profile": profile(team.event_id, member.member_id)}
                              for member in team.memberships.filter(state="requested")] if leader else []}
