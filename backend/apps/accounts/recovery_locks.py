"""User-before-envelope locks without resolving accounts for invalid guesses."""

import hmac

from apps.accounts.models import PasswordResetEnvelope, PasswordResetEnvelopeStatus, User
from apps.accounts.password_reset_crypto import fixed_dummy_digest, otp_digest


def locked_proof(normalized, code, *, purpose, now):
    """Call inside atomic(); a preliminary digest match permits only a lock lookup.

    Stage A and final purge already hold User before invalidating envelopes. Never
    wait for that User while holding an envelope they need. The unlocked snapshot
    authorizes no mutation: generation, user binding and digest are rechecked below.
    """
    # A shared contact is never sufficient ownership. Only the current member
    # account's member-context envelope participates in archive recovery.
    snapshot = PasswordResetEnvelope.objects.filter(
        user__account_kind="member", user__email__iexact=normalized,
        context="member", makerspace__isnull=True, email_normalized=normalized,
    ).first()
    candidate = otp_digest(code, normalized)
    preliminary = hmac.compare_digest(snapshot.digest if snapshot else fixed_dummy_digest(normalized), candidate)
    user = None
    if preliminary and usable(snapshot, purpose, now):
        user = User.objects.select_for_update(no_key=True).filter(pk=snapshot.user_id).first()
    envelope = (PasswordResetEnvelope.objects.select_for_update().filter(pk=snapshot.pk).first()
                if snapshot else None)
    equal = hmac.compare_digest(envelope.digest if envelope else fixed_dummy_digest(normalized), candidate)
    if (not user or not snapshot or not envelope or envelope.user_id != user.pk
            or envelope.generation != snapshot.generation
            or envelope.context != "member" or envelope.makerspace_id is not None
            or envelope.credential_generation != user.credential_generation):
        user = None
    return envelope, user, equal


def usable(row, purpose, now):
    return bool(row and row.purpose == purpose and row.digest_is_live
                and row.status == PasswordResetEnvelopeStatus.ISSUED and not row.consumed_at
                and row.expires_at and row.expires_at > now and row.attempts < 5)
