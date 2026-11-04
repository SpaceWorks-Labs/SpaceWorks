"""Attested phone sessions; one-time inputs commit before grant creation."""

import logging

from rest_framework.exceptions import APIException, AuthenticationFailed

from apps.accounts import audit_events
from apps.accounts.attestation import (
    AttestationRejected, AttestationUnavailable,
    consume_attestation_challenge, verify_attestation,
)
from apps.accounts.mfa_challenges import start
from apps.accounts.mfa_policy import needs_challenge
from apps.accounts.mfa_sessions import context, device_context
from apps.accounts.serializers import user_payload
from apps.accounts.serializers_device import DeviceGrantSerializer
from apps.accounts.services_device_grants import (
    DeviceGrantCreationRetryRequired, DeviceSuperadminNotSupported,
    assert_grant_user_allowed, audit_grant_refusal, issue_first_device_session,
)
from apps.accounts.services_device_tokens import assert_mobile_grant_creation_enabled
from apps.accounts.services_phone import confirm_login_challenge
from apps.backup.recovery import assert_token_issuance_allowed

logger = logging.getLogger(__name__)
NATIVE_PLATFORM = {"ios": "apple", "android": "android"}


class PhoneDeviceError(APIException):
    def __init__(self, *, unavailable=False):
        self.status_code = 503 if unavailable else 409
        code = "attestation_unavailable" if unavailable else "phone_device_restart_required"
        super().__init__({
            "code": code,
            "detail": (
                "Device attestation is unavailable. Restart with a new code and challenge."
                if unavailable else "Restart phone sign-in with a new code and attestation challenge."
            ),
        }, code=code)


def complete_phone_device_login(request, data):
    # #162(3): an app older than the platform minimum is refused before the code is spent.
    from apps.accounts.native_app_version import assert_supported
    assert_supported(NATIVE_PLATFORM.get(data["client_platform"]), data.get("app_version"))
    # Never put this inside the grant transaction: failed_attempts and a successful
    # OTP's consumed_at must survive every subsequent attestation/issuance failure.
    user, otp = confirm_login_challenge(data["phone"], data["code"], delivery="device")
    try:
        challenge = consume_attestation_challenge(
            data["challenge"], expected_id=otp.attestation_challenge_id,
        )
        if challenge is None:
            raise AttestationRejected("Attestation was rejected.")
        platform = "ios" if challenge.platform == "apple" else "android"
        if data["client_platform"] != platform:
            raise AttestationRejected("Attestation was rejected.")
        verified = verify_attestation(challenge, data["challenge"], data["attestation"])
        assert_mobile_grant_creation_enabled()
        assert_token_issuance_allowed(user)
        if needs_challenge(user):
            try:
                assert_grant_user_allowed(user)
            except DeviceSuperadminNotSupported as exc:
                audit_grant_refusal(exc)
                raise
            return start(user, context=context(
                request, surface="member",
                device=device_context(challenge, verified, login_method="phone"),
            ))
        access, refresh, grant = issue_first_device_session(
            user, challenge, verified, login_method="phone",
        )
    except AttestationUnavailable as exc:
        _audit_failure(user, "attestation_unavailable")
        raise PhoneDeviceError(unavailable=True) from exc
    except (AttestationRejected, DeviceGrantCreationRetryRequired, AuthenticationFailed) as exc:
        _audit_failure(user, "device_restart_required")
        raise PhoneDeviceError() from exc
    request.device_grant = grant
    audit_events.record_auth_event(
        user, "auth.phone_login_succeeded", target=user,
        meta={"phone_hash": audit_events.fingerprint(user.phone_e164)},
    )
    from apps.accounts.login_risk import record_success  # S-B: a phone code records the device (Q4)
    return {
        "access": access, "refresh": refresh,
        "device_grant": DeviceGrantSerializer(grant).data,
        "user": user_payload(user, request=request, session_authority="member"),
        "device_trust": record_success(request, user, method="phone", web=False),
    }


def _audit_failure(user, reason):
    audit_events.record_auth_event(
        user, "auth.phone_login_failed", target=user, meta={"reason": reason},
    )
    logger.warning("Phone device login refused", extra={"user_id": user.pk, "reason": reason})
