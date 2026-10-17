"""Request and confirmation services for the password-reset envelope."""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts import audit_events
from apps.accounts.models import PasswordResetEnvelope, PasswordResetEnvelopeStatus
from apps.accounts.password_reset_crypto import (
    new_dummy_digest,
    normalize_email,
)
from apps.accounts.password_reset_context import (
    lock_recovery_account, resolve_account, recoverable, mail_available, recovery_transaction,
)
from .services_password_reset_confirmation import (
    confirm_password_reset as confirm_password_reset,
    validate_recovery_password as validate_recovery_password,
)

RESEND_COOLDOWN = timedelta(seconds=60)
MAX_ATTEMPTS = 5
GENERIC_CONFIRM_ERROR = "Invalid or expired verification code."

REENTRANT_STATUSES = frozenset(
    {
        PasswordResetEnvelopeStatus.ISSUED,
        PasswordResetEnvelopeStatus.CONSUMED,
        PasswordResetEnvelopeStatus.DISCARDED,
        PasswordResetEnvelopeStatus.UNDELIVERABLE,
        PasswordResetEnvelopeStatus.DELIVERY_UNKNOWN,
    }
)
BLOCKED_STATUSES = frozenset(
    {
        PasswordResetEnvelopeStatus.PENDING,
        PasswordResetEnvelopeStatus.CLAIMED,
        PasswordResetEnvelopeStatus.DELIVERING,
    }
)


class PasswordResetCooldown(Exception):
    pass


def request_password_reset(email, *, context="member", makerspace=None, origin="", now=None):
    """Queue recovery for a context-bound account, with a generic public acknowledgement.

    A request already pending, claimed, or delivering is deliberately a no-op. In
    particular, generation fencing cannot un-send mail, so delivery owns the row until
    its SMTP outcome is known or its lease becomes ``delivery_unknown``.
    """
    identifier = str(email).strip()
    normalized = normalize_email(identifier)
    requested_at = now or timezone.now()
    # Member recovery has no origin boundary. Never store an untrusted, unbounded
    # browser header in the staff/platform-only origin field.
    origin = "" if context == "member" else origin
    cooled_down = False
    user = resolve_account(identifier, context=context, makerspace=makerspace)
    with recovery_transaction(user):
        if user:
            user = lock_recovery_account(user)
        if context != "member" and (not mail_available(context) or not recoverable(
                user, context=context, makerspace=makerspace, origin=origin)):
            user = None
        if user:
            normalized = normalize_email(user.email)
        envelope, created = _lock_or_create(user, normalized, requested_at, context=context, origin=origin) if user else (None, False)
        if envelope is not None and not created and envelope.status in REENTRANT_STATUSES:
            if envelope.requested_at > requested_at - RESEND_COOLDOWN:
                cooled_down = True
            else:
                _reenter_pending(envelope, normalized, requested_at)
                envelope.request_origin = origin
                envelope.credential_generation = user.credential_generation
                envelope.save(update_fields=["request_origin", "credential_generation"])
        elif envelope is not None and not created and envelope.status not in BLOCKED_STATUSES:
            # Fail closed if a future state is added without defining its resend rule.
            cooled_down = True
        audit_events.record_auth_event(
            None,
            "auth.password_reset_requested",
            target=envelope,
            makerspace=envelope.makerspace if envelope and context == "staff" else None,
            meta={
                "email_hash": audit_events.fingerprint(normalized),
                "method": "otp",
            },
        )
    if cooled_down:
        raise PasswordResetCooldown
    return envelope


def _lock_or_create(user, normalized, requested_at, *, context, origin):
    envelope = (
        PasswordResetEnvelope.objects.select_for_update()
        .filter(user_id=user.pk)
        .first()
    )
    if envelope is not None:
        return envelope, False
    try:
        # The savepoint is important: a concurrent first insert may win the unique
        # account constraint. Rolling back only this savepoint keeps the outer transaction
        # usable so it can lock the winner.
        with transaction.atomic():
            envelope = PasswordResetEnvelope.objects.create(
                user=user,
                context=context,
                makerspace_id=user.staff_makerspace_id if context == "staff" else None,
                request_origin=origin,
                credential_generation=user.credential_generation,
                email_normalized=normalized,
                email_fingerprint=audit_events.fingerprint(normalized),
                digest=new_dummy_digest(normalized),
                digest_is_live=False,
                generation=1,
                requested_at=requested_at,
            )
        return envelope, True
    except IntegrityError:
        envelope = PasswordResetEnvelope.objects.select_for_update().get(
            user_id=user.pk
        )
        return envelope, False


def _reenter_pending(envelope, normalized, requested_at):
    envelope.email_normalized = normalized
    envelope.email_fingerprint = audit_events.fingerprint(normalized)
    envelope.digest = new_dummy_digest(normalized)
    envelope.digest_is_live = False
    envelope.credential_fingerprint = ""
    envelope.expires_at = None
    envelope.consumed_at = None
    envelope.attempts = 0
    envelope.status = PasswordResetEnvelopeStatus.PENDING
    envelope.claimed_at = None
    envelope.claim_owner = ""
    envelope.claim_expires_at = None
    envelope.generation += 1
    envelope.requested_at = requested_at
    envelope.superseded_at = None
    envelope.terminal_at = None
    envelope.save()
