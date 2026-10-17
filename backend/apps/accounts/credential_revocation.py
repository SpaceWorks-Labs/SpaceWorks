"""Account-wide credential invalidation shared by lifecycle and recovery services."""

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import PasswordResetEnvelope, StaffInvitation, User
from apps.accounts.credential_revocation_helpers import (
    revoke_authentication, revoke_pending_proofs, revoke_reset_envelopes,
)
from apps.audit import services as audit


def revoke_all_credentials(user, *, reason, actor=None):
    """Revoke account-owned bearers, retaining credential and audit history.

    Anonymous social attempts and station/app/API-client credentials are independent
    principals, not credentials owned by this account. Established MFA factors and
    linked social identities are retained; their outstanding proofs are consumed.
    Repeating a call is safe: timestamps remain terminal and no authority is restored.
    Each explicit invalidation advances the generation, including repeated calls.
    Call this before taking an account row lock in an outer lifecycle transaction:
    recovery envelopes and invitation redemption both lock their rows before User.
    """
    return _revoke(user, reason=reason, actor=actor, all_credentials=True)


def revoke_sessions_only(user, *, reason, actor=None):
    """Password rotation seam: sessions, refresh, devices and open invitations."""
    return _revoke(user, reason=reason, actor=actor, all_credentials=False)


def _revoke(user, *, reason, actor, all_credentials):
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 200:
        raise ValueError("A non-empty revocation reason of at most 200 characters is required.")
    if user.pk is None:
        raise ValueError("Credential revocation requires a persisted account.")
    with transaction.atomic():
        # Recovery's declared order is Envelope -> User. Lock only account-bound
        # envelopes: email is shared across account kinds and is never ownership.
        envelopes = list(PasswordResetEnvelope.objects.select_for_update().filter(
            user_id=user.pk,
        ).order_by("pk")) if all_credentials else []
        # Invitation acceptance also locks its invitation before the account.
        # Keep that order for reset-vs-redemption; never join nullable account FKs.
        list(StaffInvitation.objects.select_for_update().filter(
            account_id=user.pk, accepted_at__isnull=True, revoked_at__isnull=True,
        ).order_by("pk"))
        locked = User.objects.select_for_update().get(pk=user.pk)
        now = timezone.now()
        locked.credential_generation += 1
        locked.save(update_fields=["credential_generation"])
        counts = revoke_authentication(locked, now=now)
        if all_credentials:
            counts.update(revoke_pending_proofs(locked, now=now))
            counts["password_reset_envelopes"] = revoke_reset_envelopes(envelopes, now=now)
        audit.record(actor, "account.credentials_revoked", target=locked, meta={
            "reason": reason, "counts": counts,
            "scope": "all" if all_credentials else "sessions",
        })
    # Keep callers holding the original instance in sync, only after success.
    user.credential_generation = locked.credential_generation
    return counts
