"""Existing claim provenance and membership revocation helpers."""
from django.utils.translation import gettext
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from apps.audit import services as audit
from apps.presence.models import PresenceSession


def _active_sessions(user, makerspace, now):
    return PresenceSession.objects.select_for_update().filter(
        member=user, makerspace=makerspace, ended_at__isnull=True, expires_at__gt=now)


def end_sessions_for_membership(actor, membership, reason="membership_revoked"):
    now = timezone.now()
    for session in _active_sessions(membership.user, membership.makerspace, now):
        session.ended_at = now
        session.ended_by = actor
        session.end_reason = reason
        session.save(update_fields=["ended_at", "ended_by", "end_reason"])
        audit.record(actor, "presence.ended_membership_revoked", makerspace=membership.makerspace, target=session)


def end_sessions_for_claim(claim, *, ended_at, actor):
    """Lock claim then end exactly the active presence rows carrying its FK."""
    with transaction.atomic():
        from apps.accounts.models_claim import MemberClaimCode

        locked = (
            MemberClaimCode.objects.select_for_update(of=("self",))
            .select_related("membership")
            .get(pk=claim.pk)
        )
        if (
            locked.session_id != claim.session_id
            or locked.membership_id != claim.membership_id
        ):
            raise RuntimeError("Claim-session provenance is inconsistent.")
        sessions = list(
            PresenceSession.objects.select_for_update().filter(
                created_via_claim_session=locked,
                member_id=locked.membership.user_id,
                makerspace_id=locked.membership.makerspace_id,
                ended_at__isnull=True,
                expires_at__gt=ended_at,
            )
        )
        for session in sessions:
            session.ended_at = ended_at
            session.ended_by = actor
            session.end_reason = PresenceSession.EndReason.CLAIM_REVOKED
            session.save(update_fields=["ended_at", "ended_by", "end_reason"])
            audit.record(
                actor,
                "presence.ended_claim_revoked",
                makerspace=session.makerspace,
                target=session,
                meta={"claim_session_id": str(locked.session_id)},
            )


def expire_claim_presence(session_id):
    """End expired/revoked claim presence after a signed access token is rejected."""
    from apps.accounts.models_claim import MemberClaimCode

    claim = MemberClaimCode.objects.filter(session_id=session_id).first()
    now = timezone.now()
    if claim and (
        claim.revoked_at is not None
        or (claim.absolute_expires_at and claim.absolute_expires_at <= now)
    ):
        end_sessions_for_claim(claim, ended_at=now, actor=None)


def _validate_claim_scope(claim, user, makerspace):
    if (
        claim.membership.user_id != user.pk
        or claim.membership.makerspace_id != makerspace.pk
    ):
        raise PermissionDenied(gettext("Claim session does not belong to this member and makerspace."))
