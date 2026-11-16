"""Single-use fragment invitations: only keyed digests are persisted."""
from django.utils.translation import gettext
import hashlib
import hmac
from datetime import timedelta
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .admission_errors import check_version, fail
from .admission_transactions import command, record
from .team_models import HackathonTeam, HackathonTeamInvite, HackathonTeamMember
from .team_workflow import activate_locked, member_application, require_forming, require_leader


def digest(value, *, purpose):
    return hmac.new(settings.SECRET_KEY.encode(), ("hackathon-team:" + purpose + ":" + value).encode(), hashlib.sha256).hexdigest()


def invitation_token(team_id, actor_id, operation_id):
    # Re-creatable on authorized same-operation retry, absent from DB/receipt.
    return digest(f"{team_id}:{actor_id}:{operation_id}", purpose="issue")


def invite(*, event_id, team_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action=f"teams.invite:{team_id}", owner=True) as ctx:
        team = get_object_or_404(HackathonTeam.objects.select_for_update(), event=ctx.event, pk=team_id)
        require_leader(team, actor)
        if not data.get("revoke_only"):
            require_forming(ctx.config, team)
        token = invitation_token(team.pk, actor.pk, data["operation_id"])
        if ctx.reference:
            if data.get("revoke_only"):
                return None, None
            row = get_object_or_404(HackathonTeamInvite, team=team, pk=ctx.reference["id"])
            if row.revoked_at or row.redeemed_at or row.expires_at <= timezone.now():
                fail("invitation_expired", gettext("This invitation is no longer usable."), status=410)
            return row, token
        check_version(team, data["expected_version"])
        if data.get("rotate") or data.get("revoke_only"):
            for old in team.invites.select_for_update().filter(revoked_at__isnull=True, redeemed_at__isnull=True):
                old.revoked_at = timezone.now()
                old.save(update_fields=["revoked_at"])
                record(ctx, "team_invite_revoked", old, team_id=team.pk)
        if data.get("revoke_only"):
            team.version += 1
            team.save()
            ctx.finish("invite_revocation", team.pk)
            return None, None
        deadline = min(timezone.now() + timedelta(days=7), ctx.event.ends_at)
        if ctx.config.team_lock_at:
            deadline = min(deadline, ctx.config.team_lock_at)
        email = data.get("email", "").strip().lower()
        row = HackathonTeamInvite.objects.create(team=team, token_digest=digest(token, purpose="token"),
            email_digest=digest(email, purpose="email") if email else "", expires_at=deadline, created_by=actor)
        team.version += 1
        team.save()
        record(ctx, "team_invite_created", row, team_id=team.pk)
        from .team_notifications import emit_invite_locked
        emit_invite_locked(invite=row, email=email)
        ctx.finish("team_invite", row.pk)
        return row, token


def join_request(*, event_id, team_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action=f"teams.request:{team_id}", owner=True) as ctx:
        team = get_object_or_404(HackathonTeam.objects.select_for_update(), event=ctx.event, pk=team_id)
        if ctx.reference:
            return team
        if not ctx.config.finder_enabled or not team.seeking_members:
            fail("not_found", gettext("Not found."), status=404)
        check_version(team, data["expected_version"])
        require_forming(ctx.config, team)
        application = member_application(ctx, actor)
        if HackathonTeamMember.objects.filter(event=ctx.event, member=actor, state="active").exists():
            fail("already_in_team", gettext("You already belong to a team."))
        if team.memberships.filter(member=actor, state__in=("requested", "invited")).exists():
            fail("request_exists", gettext("Your request is already waiting."))
        row = HackathonTeamMember.objects.create(event=ctx.event, team=team, application=application, member=actor, creator=actor, state="requested")
        team.version += 1
        team.save()
        record(ctx, "team_join_requested", row, team_id=team.pk)
        from .team_notifications import emit_team_locked
        emit_team_locked(team=team, kind="team_join_requested", member_ids=(team.leader_id,), request_id=row.pk)
        ctx.finish("team", team.pk)
        return team


def decline(*, event_id, team_id, actor, data):
    """The leader says no to one join request; the requester is told and may ask another team."""
    with command(event_id=event_id, actor=actor, data=data, action=f"teams.decline:{team_id}", owner=True) as ctx:
        team = get_object_or_404(HackathonTeam.objects.select_for_update(), event=ctx.event, pk=team_id)
        require_leader(team, actor)
        if ctx.reference:
            return team
        check_version(team, data["expected_version"])
        row = get_object_or_404(team.memberships.select_for_update(), pk=data["request_id"], state="requested")
        row.state, row.left_at = "declined", timezone.now()
        row.save()
        team.version += 1
        team.save()
        record(ctx, "team_join_declined", row, team_id=team.pk)
        from .team_notifications import emit_team_locked
        emit_team_locked(team=team, kind="team_join_declined", member_ids=[row.member_id], request_id=row.pk)
        ctx.finish("team", team.pk)
        return team


def accept(*, event_id, team_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action=f"teams.accept:{team_id}", owner=True) as ctx:
        team = get_object_or_404(HackathonTeam.objects.select_for_update(), event=ctx.event, pk=team_id)
        if ctx.reference:
            if not team.memberships.filter(member=actor, state="active").exists():
                fail("not_found", gettext("Not found."), status=404)
            return team
        invitation = None
        if "request_id" in data:
            require_leader(team, actor)
            request = get_object_or_404(team.memberships.select_related("member"), pk=data["request_id"], state="requested")
            member = request.member
            from apps.events.registration_access import require_registration_access
            require_registration_access(ctx.event, member)
        else:
            invitation = team.invites.select_for_update().filter(token_digest=digest(data["token"], purpose="token")).first()
            if not invitation or invitation.revoked_at or invitation.redeemed_at or invitation.expires_at <= timezone.now():
                fail("not_found", gettext("Not found."), status=404)
            if invitation.email_digest and (not actor.email_verified_at or not actor.email or not hmac.compare_digest(
                    invitation.email_digest, digest(actor.email.strip().lower(), purpose="email"))):
                fail("not_found", gettext("Not found."), status=404)
            member = actor
        if invitation is None:
            check_version(team, data["expected_version"])
        # An invitation link carries the version it was minted at; the team keeps changing (comments, other joins),
        # so the token, its expiry and the forming/capacity checks authorise it, not that stale number (decision 296).
        require_forming(ctx.config, team)
        application = member_application(ctx, member)
        activate_locked(ctx, team, member, application)
        from .team_notifications import emit_team_locked
        emit_team_locked(team=team, kind="team_membership_updated")
        if invitation:
            invitation.redeemed_at, invitation.redeemed_by = timezone.now(), actor
            invitation.save(update_fields=["redeemed_at", "redeemed_by"])
            record(ctx, "team_invite_redeemed", invitation, team_id=team.pk)
        ctx.finish("team", team.pk)
        return team
