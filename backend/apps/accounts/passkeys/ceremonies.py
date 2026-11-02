"""One-time WebAuthn ceremonies: options out, a verified response back (py_webauthn).

Every ceremony is a ``WebAuthnCeremony`` row holding a 32-byte random challenge, the
purpose, the exact origin and RP ID it was issued for and a 5-minute expiry. Finishing
consumes it before anything is checked, so a response can never be replayed and a failed
attempt cannot be retried against the same challenge. User verification is REQUIRED for
registration, sign-in and re-authentication; a second-factor assertion after a password
asks for it but does not insist (the password was the first factor).
"""

import base64
import hashlib
import os

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException

from apps.accounts.login_security_contract import (
    CEREMONY_MFA, CEREMONY_REGISTRATION, CEREMONY_TTL, PASSKEY_FAILED,
)
from apps.accounts.models_webauthn import WebAuthnCeremony, WebAuthnCredential

MAX_PASSKEYS = 10


class PasskeyFailed(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = PASSKEY_FAILED

    def __init__(self, detail="The passkey could not be verified. Try again."):
        super().__init__({"detail": detail, "code": PASSKEY_FAILED})


def b64url(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def unb64url(value):
    value = str(value or "")
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def user_handle(user):
    """An opaque, stable WebAuthn user handle: no name, email or phone in it."""
    return hashlib.sha256(f"spaceworks:webauthn-user:{user.pk}".encode()).digest()


def _timeout_ms():
    return int(CEREMONY_TTL.total_seconds() * 1000)


def _create(purpose, *, origin, rp_id, user=None, mfa_challenge=None):
    now = timezone.now()
    return WebAuthnCeremony.objects.create(
        purpose=purpose, user=user, challenge=b64url(os.urandom(32)), rp_id=rp_id, origin=origin,
        mfa_challenge=mfa_challenge, created_at=now, expires_at=now + CEREMONY_TTL)


def _descriptors(rows):
    from webauthn.helpers.structs import AuthenticatorTransport, PublicKeyCredentialDescriptor
    known = {item.value for item in AuthenticatorTransport}
    return [PublicKeyCredentialDescriptor(
        id=unb64url(row.credential_id),
        transports=[AuthenticatorTransport(value) for value in row.transports if value in known] or None,
    ) for row in rows]


def registration_options(user, *, origin, rp_id):
    from webauthn import generate_registration_options, options_to_json
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria, ResidentKeyRequirement, UserVerificationRequirement,
    )
    ceremony = _create(CEREMONY_REGISTRATION, origin=origin, rp_id=rp_id, user=user)
    existing = WebAuthnCredential.objects.filter(user=user, rp_id=rp_id)
    options = generate_registration_options(
        rp_id=rp_id, rp_name=settings.WEBAUTHN_RP_NAME, user_name=user.username, user_id=user_handle(user),
        user_display_name=user.display_name or user.username, challenge=unb64url(ceremony.challenge),
        timeout=_timeout_ms(), exclude_credentials=_descriptors(existing),
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED, user_verification=UserVerificationRequirement.REQUIRED),
    )
    return ceremony, options_to_json(options)


def assertion_options(purpose, *, origin, rp_id, user=None, mfa_challenge=None):
    """Options for a sign-in (``user=None``: discoverable credentials, conditional UI),
    a second factor or a re-authentication. Only credentials on this RP ID are offered."""
    from webauthn import generate_authentication_options, options_to_json
    from webauthn.helpers.structs import UserVerificationRequirement
    ceremony = _create(purpose, origin=origin, rp_id=rp_id, user=user, mfa_challenge=mfa_challenge)
    allowed = WebAuthnCredential.objects.filter(user=user, rp_id=rp_id) if user is not None else []
    verification = (UserVerificationRequirement.PREFERRED if purpose == CEREMONY_MFA
                    else UserVerificationRequirement.REQUIRED)
    options = generate_authentication_options(
        rp_id=rp_id, challenge=unb64url(ceremony.challenge), timeout=_timeout_ms(),
        allow_credentials=_descriptors(allowed), user_verification=verification)
    return ceremony, options_to_json(options)


def consume(ceremony_id, purpose, *, origin):
    """Lock and consume one ceremony in its own transaction, so it is spent whatever
    happens next (call it outside any outer atomic block that a failure rolls back)."""
    from django.core.exceptions import ValidationError
    now = timezone.now()
    with transaction.atomic():
        try:
            ceremony = WebAuthnCeremony.objects.select_for_update().filter(pk=ceremony_id, purpose=purpose).first()
        except (ValidationError, ValueError, TypeError):
            ceremony = None
        if ceremony is None or ceremony.consumed_at is not None or ceremony.expires_at <= now:
            raise PasskeyFailed("This passkey request expired. Start again.")
        ceremony.consumed_at = now
        ceremony.save(update_fields=["consumed_at"])
    if ceremony.origin != origin:
        raise PasskeyFailed()
    return ceremony


def verify_registration(ceremony, credential):
    from webauthn import verify_registration_response
    try:
        return verify_registration_response(
            credential=credential, expected_challenge=unb64url(ceremony.challenge),
            expected_rp_id=ceremony.rp_id, expected_origin=ceremony.origin, require_user_verification=True)
    except Exception as exc:  # malformed JSON, bad attestation, wrong origin/RP: one answer
        raise PasskeyFailed() from exc


def _credential_id(credential):
    if not isinstance(credential, dict):
        raise PasskeyFailed()
    raw = credential.get("rawId") or credential.get("id")
    try:
        return b64url(unb64url(raw)) if raw else ""
    except (ValueError, TypeError):
        return ""


@transaction.atomic
def verify_assertion(ceremony, credential, *, user=None):
    """Verify an assertion against the ceremony and a stored credential; return the
    locked ``WebAuthnCredential`` with its counters updated. ``user`` (when given) must
    own it. A sign-count regression (a cloned authenticator) fails like any other check.
    """
    from webauthn import verify_authentication_response
    row = WebAuthnCredential.objects.select_for_update().filter(
        credential_id=_credential_id(credential), rp_id=ceremony.rp_id).first()
    expected_user = user if user is not None else ceremony.user
    if row is None or (expected_user is not None and row.user_id != expected_user.pk):
        raise PasskeyFailed()
    try:
        verified = verify_authentication_response(
            credential=credential, expected_challenge=unb64url(ceremony.challenge),
            expected_rp_id=ceremony.rp_id, expected_origin=ceremony.origin,
            credential_public_key=bytes(row.public_key), credential_current_sign_count=row.sign_count,
            require_user_verification=ceremony.purpose != CEREMONY_MFA)
    except Exception as exc:
        raise PasskeyFailed() from exc
    row.sign_count, row.backed_up, row.last_used_at = verified.new_sign_count, verified.credential_backed_up, timezone.now()
    row.save(update_fields=["sign_count", "backed_up", "last_used_at"])
    return row
