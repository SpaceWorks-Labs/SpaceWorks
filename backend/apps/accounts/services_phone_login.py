"""Anonymous phone-login half of the OTP service."""

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.accounts import audit_events
from apps.accounts.models import User
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


def start_login(raw_phone):
    """Send a login code without revealing whether the number is known."""
    if not sms_configured():
        raise SmsUnavailable
    phone_e164 = normalize_or_none(raw_phone)
    if phone_e164 is None:
        return None
    user = User.objects.filter(
        account_kind="member",
        phone_e164=phone_e164,
        phone_verified_at__isnull=False,
        is_tenant_dump_stub=False,
        is_active=True,
        access_status=User.AccessStatus.ACTIVE,
    ).first()
    if user is None:
        return None
    try:
        challenge, sent = _issue(user, phone_e164, PhoneChallengePurpose.LOGIN)
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
    phone_e164 = normalize_or_none(raw_phone)
    if phone_e164 is None:
        raise serializers.ValidationError({"detail": GENERIC_CONFIRM_ERROR})
    user = None
    with transaction.atomic():
        # Revocation locks User before consuming phone proofs. Resolve ownership
        # without locking, then follow that same order and recheck the OTP below.
        candidate_id = PhoneVerificationChallenge.objects.filter(
            purpose=PhoneChallengePurpose.LOGIN, user__account_kind="member",
            phone_e164=phone_e164, consumed_at__isnull=True,
            failed_attempts__lt=MAX_FAILED_ATTEMPTS, expires_at__gt=timezone.now(),
        ).order_by("-created_at").values_list("user_id", flat=True).first()
        if candidate_id is not None:
            User.objects.select_for_update(no_key=True).get(pk=candidate_id)
        challenge = _confirm(
            PhoneVerificationChallenge.objects.filter(
                purpose=PhoneChallengePurpose.LOGIN, user__account_kind="member",
                user_id=candidate_id,
            ),
            code,
            phone_e164,
            on_failure=lambda row: audit_events.record_auth_event(
                getattr(row, "user", None),
                "auth.phone_login_failed",
                meta={"phone_hash": audit_events.fingerprint(phone_e164)},
            ),
        )
        if challenge is not None:
            user = (
                User.objects.select_for_update()
                .filter(
                    pk=challenge.user_id,
                    account_kind="member",
                    phone_e164=phone_e164,
                    phone_verified_at__isnull=False,
                    is_tenant_dump_stub=False,
                    is_active=True,
                    access_status=User.AccessStatus.ACTIVE,
                )
                .first()
            )
    if user is None:
        raise serializers.ValidationError({"detail": GENERIC_CONFIRM_ERROR})
    return user
