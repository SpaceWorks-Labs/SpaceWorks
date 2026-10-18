"""Phone recovery consumes the existing login-start OTP and exact app proof."""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts import audit_events
from apps.accounts.account_restore import matches, restore_locked
from apps.accounts.models import User
from apps.accounts.models_phone import PhoneVerificationChallenge
from apps.accounts.phone_numbers import normalize_or_none
from apps.accounts.services_phone import _confirm


def confirm_phone(data):
    phone = normalize_or_none(data["phone"])
    if phone is None:
        raise ValidationError({"detail": "Invalid or expired restore proof."})
    # Attempts and successful consumption must survive a failed attestation or restore.
    with transaction.atomic():
        otp = _confirm(PhoneVerificationChallenge.objects.filter(
            purpose="restore", attestation_challenge__isnull=data["delivery"] == "web"),
            data["code"], phone, on_failure=lambda row: audit_events.record_auth_event(
                None, "auth.account_restore_attempted", target=row))
        if otp is not None:
            audit_events.record_auth_event(None, "auth.account_restore_attempted", target=otp)
    if otp is None:
        raise ValidationError({"detail": "Invalid or expired restore proof."})
    if data["delivery"] == "device":
        from apps.accounts.attestation import (consume_attestation_challenge, verify_attestation,
                                               AttestationRejected, AttestationUnavailable)
        from apps.accounts.services_phone_device import PhoneDeviceError
        try:
            challenge = consume_attestation_challenge(data["challenge"], expected_id=otp.attestation_challenge_id)
            if challenge is None or data["client_platform"] != ("ios" if challenge.platform == "apple" else "android"):
                raise AttestationRejected("Attestation was rejected.")
            verify_attestation(challenge, data["challenge"], data["attestation"])
        except AttestationUnavailable as exc:
            raise PhoneDeviceError(unavailable=True) from exc
        except AttestationRejected as exc:
            raise PhoneDeviceError() from exc
    with transaction.atomic():
        user = User.objects.select_for_update(no_key=True).filter(pk=otp.user_id).first()
        if (otp.expires_at <= timezone.now() or not matches(user, otp.credential_fingerprint)
                or user.email or user.phone_e164 != phone):
            raise ValidationError({"detail": "Invalid or expired restore proof."})
        return restore_locked(user, fingerprint=otp.credential_fingerprint, new_password=data["new_password"])
