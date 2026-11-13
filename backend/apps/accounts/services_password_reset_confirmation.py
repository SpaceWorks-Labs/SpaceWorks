"""Consume context-bound recovery OTPs under the credential lock order."""

import hmac
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers
from apps.accounts import audit_events
from apps.accounts.models import PasswordResetEnvelope, PasswordResetEnvelopeStatus
from apps.accounts.credential_revocation import revoke_sessions_only
from apps.accounts.password_reset_context import (
    lock_recovery_account, resolve_account, recoverable, recovery_transaction,
)
from apps.accounts.password_reset_crypto import (credential_fingerprint, fixed_dummy_digest,
    new_dummy_digest, normalize_email, otp_digest)

MAX_ATTEMPTS = 5
GENERIC_CONFIRM_ERROR = "Invalid or expired verification code."

def confirm_password_reset(email, code, new_password, *, context="member", makerspace=None, origin="", now=None):
    """Consume a live OTP and rotate the bound account credential.

    Credential ownership is locked before the envelope. All errors whose
    counters or terminal state must persist are raised only after the atomic block.
    """
    identifier = str(email).strip()
    account = resolve_account(identifier, context=context, makerspace=makerspace)
    normalized = normalize_email(account.email if account and account.email else identifier)
    confirmed_at = now or timezone.now()
    failure = {"detail": GENERIC_CONFIRM_ERROR}
    password_failure = None
    confirmed_user = None

    with recovery_transaction(account):
        user = lock_recovery_account(account)
        envelope = PasswordResetEnvelope.objects.select_for_update().filter(
            user_id=user.pk, context=context, makerspace_id=None,
        ).first() if user else None
        stored_digest = (
            envelope.digest if envelope is not None else fixed_dummy_digest(normalized)
        )
        # Nothing may branch on digest_is_live until this constant-time comparison has
        # happened. Unknown and non-live rows therefore pay the same cryptographic work.
        digest_matches = hmac.compare_digest(
            stored_digest, otp_digest(str(code), normalized)
        )
        attempts_before = envelope.attempts if envelope is not None else MAX_ATTEMPTS
        if envelope is not None:
            envelope.attempts = min(envelope.attempts + 1, MAX_ATTEMPTS)
            envelope.save(update_fields=["attempts"])
        audit_events.record_auth_event(
            None,
            "auth.password_reset_confirm_attempted",
            target=envelope,
            meta={"method": "otp"},
        )

        stage_one_passes = bool(
            envelope is not None
            and digest_matches
            and envelope.digest_is_live
            and envelope.status == PasswordResetEnvelopeStatus.ISSUED
            and envelope.consumed_at is None
            and envelope.expires_at is not None
            and envelope.expires_at > confirmed_at
            and attempts_before < MAX_ATTEMPTS
        )
        if stage_one_passes:
            if not _credential_state_matches(user, envelope, normalized, makerspace=makerspace, origin=origin):
                _discard_locked(envelope, confirmed_at, superseded=True)
            else:
                try:
                    validate_recovery_password(new_password, user)
                except DjangoValidationError as exc:
                    from apps.accounts.password_breach import error_body
                    password_failure = error_body("new_password", exc)
                else:
                    user.set_password(new_password)
                    user.must_change_password = False
                    user.save(update_fields=["password", "must_change_password"])
                    revoke_sessions_only(user, reason=f"{context}.password_reset", actor=user)
                    envelope.status = PasswordResetEnvelopeStatus.CONSUMED
                    envelope.consumed_at = confirmed_at
                    envelope.terminal_at = confirmed_at
                    envelope.digest = new_dummy_digest(normalized)
                    envelope.digest_is_live = False
                    envelope.save(
                        update_fields=[
                            "status",
                            "consumed_at",
                            "terminal_at",
                            "digest",
                            "digest_is_live",
                        ]
                    )
                    audit_events.record_auth_event(
                        user,
                        "user.password_reset_via_email",
                        target=user,
                        meta={"method": "otp"},
                    )
                    alert_reset(user)
                    confirmed_user = user

    if password_failure is not None:
        raise serializers.ValidationError(password_failure)
    if confirmed_user is None:
        raise serializers.ValidationError(failure)
    return confirmed_user


def _credential_state_matches(user, envelope, normalized, *, makerspace=None, origin=""):
    return bool(
        envelope.purpose == "reset"
        and user.deletion_requested_at is None
        and (user.account_restored_at is None or envelope.requested_at > user.account_restored_at)
        and recoverable(user, context=envelope.context, makerspace=makerspace, origin=origin)
        and normalize_email(user.email) == envelope.email_normalized == normalized
        and user.credential_generation == envelope.credential_generation
        and hmac.compare_digest(envelope.credential_fingerprint, credential_fingerprint(user, normalized))
    )


def validate_recovery_password(new_password, user):
    """Run candidate-password checks only after the caller has proved possession."""
    if not new_password:
        raise DjangoValidationError("This password may not be blank.")
    validate_password(new_password, user=user)


def _discard_locked(envelope, now, *, superseded=False):
    envelope.status = PasswordResetEnvelopeStatus.DISCARDED
    envelope.digest = new_dummy_digest(envelope.email_normalized)
    envelope.digest_is_live = False
    envelope.credential_fingerprint = ""
    envelope.expires_at = None
    envelope.terminal_at = now
    if superseded:
        envelope.superseded_at = now
    envelope.save(
        update_fields=[
            "status",
            "digest",
            "digest_is_live",
            "credential_fingerprint",
            "expires_at",
            "terminal_at",
            "superseded_at",
        ]
    )


def alert_reset(user):
    """S-B: a completed reset expires every outstanding alert link, then alerts afresh."""
    from apps.accounts import security_alerts
    from apps.accounts.security_not_me import expire_outstanding
    expire_outstanding(user)
    security_alerts.password_changed(user)
