"""Team notices bind actual team/invitation rows; never persist bearer links."""
from django.utils.translation import gettext, gettext_noop
import hmac
from django.utils import timezone
from apps.accounts.staff_identity import person_q
from apps.accounts.models import User
from apps.integrations.notification_outbox import emit
from apps.integrations.notification_sources import NotificationSource, register_source
from .team_models import HackathonTeam, HackathonTeamInvite
from apps.integrations.fanout_jobs import deferred_fanout

TEAM_SOURCE = "events.team"
INVITE_SOURCE = "events.team_invite"
MESSAGES = {
    "team_join_requested": gettext_noop("A participant asked to join your team."),
    "team_membership_updated": gettext_noop("Your event team membership changed."),
    "team_eligibility_changed": gettext_noop("Your event team needs to review its roster eligibility."),
    "team_reopened": gettext_noop("The event team reopened your roster for review."),
    "team_disbanded": gettext_noop("Your event team was disbanded."),
    "team_leadership_transferred": gettext_noop("You are now the leader of your event team."),
    "team_member_removed": gettext_noop("You were removed from an event team."),
    "team_join_declined": gettext_noop("The team leader declined your request to join their event team."),
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
    if team is None or team.event.makerspace_id != envelope.makerspace_id or not programme_live(team.event):
        return False
    # The team keeps changing after a decision (comments, other joins), so the version is NOT compared: the
    # recipient and ids were captured when the decision was made and only that fact must still hold.
    rows = team.memberships.filter(member_id=envelope.recipient_id)
    if envelope.event == "team_join_requested":
        return team.leader_id == envelope.recipient_id and team.memberships.filter(
            pk=envelope.context.get("request_id"), state="requested").exists()
    if envelope.event == "team_join_declined":
        return rows.filter(pk=envelope.context.get("request_id"), state="declined").exists()
    if envelope.event == "team_member_removed":
        return rows.filter(state="removed").exists()
    return rows.exists()


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
    """Capture the recipients NOW (the decision's own roster), then hand plain ids to the fan-out job."""
    if kind not in MESSAGES:
        raise ValueError("Unknown team notice.")
    members = list(member_ids) if member_ids is not None else list(
        team.memberships.filter(state="active").values_list("member_id", flat=True))
    deliver_team_notice(team, kind, members, team.version, request_id)


@deferred_fanout()
def deliver_team_notice(team, kind, members, version, request_id=None):
    for user in User.objects.filter(person_q(), pk__in=members, is_active=True,
            access_status="active", is_tenant_dump_stub=False):
        emit(makerspace=team.event.makerspace, recipient=user, feature="events", stream="events",
            event=kind, audience="member", source_kind=TEAM_SOURCE, source_id=str(team.pk), revision=str(version),
            subject=team, dedup_key=f"event-team:{team.pk}:{version}:{kind}:{request_id or 0}:{user.pk}",
            context={"event_id": team.event_id, **({"request_id": request_id} if request_id else {})},
            rendered=lambda kind=kind: {"subject": gettext("Your event team"), "text": gettext(MESSAGES[kind])})


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
        context={"event_id": invite.team.event_id}, rendered=lambda: {"subject": gettext("Event team invitation"),
            "text": gettext("You have been invited to an event team. Use the private invitation link shared by its leader.")})


def register():
    register_source(TEAM_SOURCE, NotificationSource(team_eligible))
    register_source(INVITE_SOURCE, NotificationSource(invite_eligible))
