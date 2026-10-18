"""Account-wide credential invalidation shared by lifecycle and recovery services."""

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import PasswordResetEnvelope
from apps.accounts.credential_locks import lock_credentials
from apps.accounts.credential_revocation_helpers import (
    revoke_authentication, revoke_pending_proofs, revoke_reset_envelopes,
)
from apps.audit import services as audit


@transaction.atomic
def revoke_account_sessions(user):
    """Account utility: User first, without later tenant/invitation locks."""
    from apps.accounts.session_issuance import lock_session_user

    locked = lock_session_user(user)
    locked.credential_generation += 1
    locked.save(update_fields=["credential_generation"])
    counts = revoke_authentication(locked, now=timezone.now(), revoke_invitations=False)
    user.credential_generation = locked.credential_generation
    return counts


def revoke_all_credentials(user, *, reason, actor=None):
    """Revoke account-owned bearers, retaining credential and audit history.

    Anonymous social attempts and station/app/API-client credentials are independent
    principals, not credentials owned by this account. Established MFA factors and
    linked social identities are retained; their outstanding proofs are consumed.
    Repeating a call is safe: timestamps remain terminal and no authority is restored.
    Each explicit invalidation advances the generation, including repeated calls.
    All credential writers share Tenant -> Invitations -> User -> Envelopes order.
    Call this before taking an account row lock in an outer lifecycle transaction.
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
        locked = lock_credentials(user)
        # Email is shared across kinds and never establishes account ownership.
        envelopes = list(PasswordResetEnvelope.objects.select_for_update().filter(
            user_id=user.pk,
        ).order_by("pk")) if all_credentials else []
        now = timezone.now()
        locked.credential_generation += 1
        locked.save(update_fields=["credential_generation"])
        counts = revoke_authentication(locked, now=now)
        if all_credentials:
            counts.update(revoke_pending_proofs(locked, now=now))
            counts["password_reset_envelopes"] = revoke_reset_envelopes(envelopes, now=now)
        audit.record(actor, "account.credentials_revoked", target=locked,
                     makerspace=locked.staff_makerspace, meta={
            "reason": reason, "counts": counts,
            "scope": "all" if all_credentials else "sessions",
        })
    # Keep callers holding the original instance in sync, only after success.
    user.credential_generation = locked.credential_generation
    return counts
