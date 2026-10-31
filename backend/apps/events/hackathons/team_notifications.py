"""Team notices bind actual team/invitation rows; never persist bearer links."""
import hmac
from django.utils import timezone
from apps.accounts.staff_identity import person_q
from apps.accounts.models import User
from apps.integrations.notification_outbox import emit
from apps.integrations.notification_sources import NotificationSource, register_source
from .team_models import HackathonTeam, HackathonTeamInvite

TEAM_SOURCE = "events.team"
INVITE_SOURCE = "events.team_invite"
MESSAGES = {
    "team_join_requested": "A participant asked to join your team.",
    "team_membership_updated": "Your event team membership changed.",
    "team_eligibility_changed": "Your event team needs to review its roster eligibility.",
    "team_reopened": "The event team reopened your roster for review.",
    "team_disbanded": "Your event team was disbanded.",
}


def programme_live(event):
    from apps.makerspaces.platform import feature_enabled, module_enabled
    from apps.makerspaces.servability import is_servable
    from .admission_models import HackathonConfig
    return bool(is_servable(event.makerspace) and module_enabled(event.makerspace, "events")
        and feature_enabled(event.makerspace, "events.hackathons")
        and HackathonConfig.objects.filter(event=event, enabled=True).exists())


def team_eligible(envelope):
    if envelope.event not in MESSAGES:
        return False
    if not User.objects.filter(person_q(), pk=envelope.recipient_id, is_active=True,
            access_status="active", is_tenant_dump_stub=False).exists():
        return False
    team = HackathonTeam.objects.select_related("event__makerspace").filter(pk=envelope.source_id,
        event_id=envelope.context.get("event_id")).first()
    if team is None or team.event.makerspace_id != envelope.makerspace_id or str(team.version) != envelope.revision:
        return False
    if not programme_live(team.event):
        return False
    if envelope.event == "team_join_requested":
        return team.leader_id == envelope.recipient_id and team.state == "forming" and team.memberships.filter(
            pk=envelope.context.get("request_id"), state="requested").exists()
    rows = team.memberships.filter(member_id=envelope.recipient_id)
    return rows.exists() if team.state == "disbanded" else rows.filter(state="active").exists()


def invite_eligible(envelope):
    if envelope.event != "team_invited" or envelope.revision != "1":
        return False
    row = HackathonTeamInvite.objects.select_related("team__event__makerspace").filter(
        pk=envelope.source_id, team__event_id=envelope.context.get("event_id")).first()
    user = User.objects.filter(person_q(), pk=envelope.recipient_id, is_active=True,
        access_status="active", is_tenant_dump_stub=False, email_verified_at__isnull=False).first()
    if (row is None or user is None or row.team.event.makerspace_id != envelope.makerspace_id
            or not programme_live(row.team.event) or row.revoked_at or row.redeemed_at
            or row.expires_at <= timezone.now() or row.team.state != "forming"
            or row.team.event.status != "published" or row.team.event.ends_at <= timezone.now()):
        return False
    from .team_invitations import digest
    return bool(row.email_digest and user.email and hmac.compare_digest(row.email_digest,
        digest(user.email.strip().lower(), purpose="email")))


def emit_team_locked(*, team, kind, member_ids=None, request_id=None):
    if kind not in MESSAGES:
        raise ValueError("Unknown team notice.")
    members = member_ids if member_ids is not None else team.memberships.filter(state="active").values_list("member_id", flat=True)
    for user in User.objects.filter(person_q(), pk__in=members, is_active=True,
            access_status="active", is_tenant_dump_stub=False):
        emit(makerspace=team.event.makerspace, recipient=user, feature="events", stream="events",
            event=kind, audience="member", source_kind=TEAM_SOURCE, source_id=str(team.pk), revision=str(team.version),
            subject=team, dedup_key=f"event-team:{team.pk}:{team.version}:{kind}:{user.pk}",
            context={"event_id": team.event_id, **({"request_id": request_id} if request_id else {})},
            rendered={"subject": "Your event team", "text": MESSAGES[kind]})


def emit_invite_locked(*, invite, email):
    if not email:
        return  # A generic share link has no identified recipient to notify.
    users = list(User.objects.filter(person_q(), email__iexact=email, is_active=True,
        access_status="active", is_tenant_dump_stub=False, email_verified_at__isnull=False)[:2])
    if len(users) != 1:
        return  # Never guess identity from ambiguous or unverified contact strings.
    user = users[0]
    emit(makerspace=invite.team.event.makerspace, recipient=user, feature="events", stream="events",
        event="team_invited", audience="member", source_kind=INVITE_SOURCE, source_id=str(invite.pk), revision="1",
        subject=invite, dedup_key=f"event-team-invite:{invite.pk}:{user.pk}",
        context={"event_id": invite.team.event_id}, rendered={"subject": "Event team invitation",
            "text": "You have been invited to an event team. Use the private invitation link shared by its leader."})


def register():
    register_source(TEAM_SOURCE, NotificationSource(team_eligible))
    register_source(INVITE_SOURCE, NotificationSource(invite_eligible))
