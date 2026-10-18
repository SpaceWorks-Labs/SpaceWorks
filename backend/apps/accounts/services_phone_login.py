"""Anonymous phone-login half of the OTP service."""

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.accounts import audit_events
from apps.accounts.attestation import live_approved_challenge
from apps.accounts.models import User
from apps.accounts.account_restore import restorable
from apps.accounts.models_phone import PhoneChallengePurpose, PhoneVerificationChallenge
from apps.accounts.phone_numbers import normalize_or_none
from apps.integrations.sms import sms_configured

from .services_phone import (
    ChallengeCooldown,
    GENERIC_CONFIRM_ERROR,
    MAX_FAILED_ATTEMPTS,
    SmsUnavailable,
    _confirm,
    _issue,
)


def start_login(raw_phone, *, delivery="web", client_platform="web", challenge=None):
    """Send a login code without revealing whether the number is known."""
    if not sms_configured():
        raise SmsUnavailable
    attestation_challenge = None
    if delivery == "device":
        attestation_challenge = live_approved_challenge(challenge)
        if attestation_challenge is None:
            return None
        expected = "ios" if attestation_challenge.platform == "apple" else "android"
        if client_platform != expected:
            return None
    phone_e164 = normalize_or_none(raw_phone)
    if phone_e164 is None:
        return None
    user = User.objects.filter(
        account_kind="member",
        phone_e164=phone_e164,
        phone_verified_at__isnull=False,
        is_tenant_dump_stub=False,
        access_status=User.AccessStatus.ACTIVE,
    ).first()
    archived = bool(user and not user.email and restorable(user))
    if user is None or (not archived and (not user.is_active or user.deletion_requested_at)):
        return None
    try:
        challenge, sent = _issue(
            user, phone_e164, PhoneChallengePurpose.RESTORE if archived else PhoneChallengePurpose.LOGIN,
            attestation_challenge=attestation_challenge,
        )
    except ChallengeCooldown:
        return None
    audit_events.record_auth_event(
        user,
        "auth.phone_login_requested",
        target=user,
        meta={"phone_hash": audit_events.fingerprint(phone_e164), "sms_sent": sent},
    )
    return challenge


def confirm_login(raw_phone, code):
    """Resolve the member behind a valid login code, or raise a generic 400."""
    user, _challenge = confirm_login_challenge(raw_phone, code, delivery="web")
    return user


def confirm_login_challenge(raw_phone, code, *, delivery):
    """Commit OTP consumption/failed attempts before any device verification can fail."""
    phone_e164 = normalize_or_none(raw_phone)
    if phone_e164 is None:
        raise serializers.ValidationError({"detail": GENERIC_CONFIRM_ERROR})
    candidates = PhoneVerificationChallenge.objects.filter(
        purpose=PhoneChallengePurpose.LOGIN, user__account_kind="member",
        attestation_challenge__isnull=(delivery == "web"),
    )
    # Discovery only. Revalidate this exact challenge under User -> challenge
    # locks, the same order departure uses when consuming outstanding proofs.
    candidate = candidates.filter(
        phone_e164=phone_e164, consumed_at__isnull=True,
        failed_attempts__lt=MAX_FAILED_ATTEMPTS, expires_at__gt=timezone.now(),
    ).order_by("-created_at").values("pk", "user_id").first()
    user = None
    with transaction.atomic():
        owner = (User.objects.select_for_update(no_key=True).filter(pk=candidate["user_id"]).first()
                 if candidate else None)
        challenge = _confirm(
            candidates.filter(pk=candidate["pk"], user=owner) if owner else candidates.none(),
            code,
            phone_e164,
            on_failure=lambda row: audit_events.record_auth_event(
                getattr(row, "user", None),
                "auth.phone_login_failed",
                meta={"phone_hash": audit_events.fingerprint(phone_e164)},
            ),
        )
        if challenge is not None:
            if (owner.account_kind == "member" and owner.phone_e164 == phone_e164 and owner.phone_verified_at is not None
                    and not owner.is_tenant_dump_stub and owner.is_active
                    and owner.deletion_requested_at is None
                    and owner.access_status == User.AccessStatus.ACTIVE):
                user = owner
            if user is None:
                audit_events.record_auth_event(
                    challenge.user, "auth.phone_login_failed",
                    meta={"phone_hash": audit_events.fingerprint(phone_e164),
                          "reason": "account_unavailable"},
                )
    if user is None:
        raise serializers.ValidationError({"detail": GENERIC_CONFIRM_ERROR})
    return user, challenge
