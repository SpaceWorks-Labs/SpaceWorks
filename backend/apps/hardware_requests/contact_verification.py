"""One-time email codes for account-less borrow requests (owner decision #80).

A space without member accounts lets a public borrower ask with name, phone and email.
The email must be proven before the request exists, so nobody can file a request against
someone else's address. This reuses the member sign-up OTP machinery rather than a second
implementation: the `EmailVerificationChallenge` table, its code generator and HMAC
digest, its 10-minute expiry, 60-second resend cooldown and 5-attempt cap, the platform
OTP quota and the same verification mail.

Two differences, both deliberate: a challenge is owned by the makerspace's inert
`anonymous_requester` principal (there is no borrower account), and its `email` column
holds a per-makerspace fingerprint of the address, never the address itself -- the only
plaintext copy is the request's encrypted contact snapshot.
"""

import hmac
import logging

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import Throttled, ValidationError

from apps.accounts.audit_events import fingerprint
from apps.accounts.models import EmailVerificationChallenge
from apps.accounts.services_registration import (
    CHALLENGE_TTL,
    GENERIC_CONFIRM_ERROR,
    RESEND_COOLDOWN,
    _digest,
    _generate_otp,
)
from apps.audit import services as audit
from apps.makerspaces.anonymous_requesters import get_or_create_anonymous_requester

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 5


def normalize_email(email):
    return str(email or "").strip().lower()


def email_key(makerspace, email):
    return fingerprint(f"borrower-email:{makerspace.pk}:{normalize_email(email)}")


def _usable(principal, key, now):
    return EmailVerificationChallenge.objects.filter(
        user=principal, email=key, consumed_at__isnull=True,
        failed_attempts__lt=MAX_ATTEMPTS, expires_at__gt=now,
    )


def issue_code(makerspace, email):
    """Create a fresh code for this address and mail it. Never reveals delivery state."""
    from apps.integrations.email import send_email_verification_otp
    from apps.makerspaces.limits import reserve_platform_otp_quota

    now = timezone.now()
    email = normalize_email(email)
    principal = get_or_create_anonymous_requester(makerspace)
    key = email_key(makerspace, email)
    with transaction.atomic():
        if EmailVerificationChallenge.objects.filter(
            user=principal, email=key, last_sent_at__gte=now - RESEND_COOLDOWN,
        ).exists():
            raise Throttled(wait=RESEND_COOLDOWN.total_seconds())
        _usable(principal, key, now).update(consumed_at=now)
        code = _generate_otp()
        EmailVerificationChallenge.objects.create(
            user=principal, email=key, code_digest=_digest(code),
            expires_at=now + CHALLENGE_TTL, last_sent_at=now,
        )
        quota_reserved = reserve_platform_otp_quota()
    sent = False
    if quota_reserved:
        try:
            sent = bool(send_email_verification_otp(email, code))
        except Exception:
            logger.exception("borrower_email_code_dispatch_failed")
    audit.record(None, "request.contact_code_sent", makerspace=makerspace,
                 meta={"email_hash": key, "email_sent": sent})


def consume_code(makerspace, email, code):
    """Consume the newest usable code for this address, or refuse with one generic error.

    A wrong code burns an attempt and is audited in its own committed transaction, so a
    later rollback of the caller cannot reopen the guess.
    """
    now = timezone.now()
    principal = get_or_create_anonymous_requester(makerspace)
    key = email_key(makerspace, email)
    with transaction.atomic():
        challenge = (
            _usable(principal, key, now).select_for_update().order_by("-created_at").first()
        )
        matched = challenge is not None and hmac.compare_digest(
            challenge.code_digest, _digest(str(code or "").strip()),
        )
        if matched:
            challenge.consumed_at = now
            challenge.save(update_fields=["consumed_at"])
        else:
            if challenge is not None:
                challenge.failed_attempts += 1
                challenge.save(update_fields=["failed_attempts"])
            audit.record(None, "request.contact_code_failed", makerspace=makerspace,
                         meta={"email_hash": key})
    if not matched:
        raise ValidationError({"email_code": GENERIC_CONFIRM_ERROR})
    return challenge
