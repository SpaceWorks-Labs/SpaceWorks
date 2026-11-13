"""Which second factors a challenge offers, and checking the one the person answered.

``factors[]`` in a challenge response lists, in ``login_security_contract.FACTORS`` order:
``totp`` (an enabled authenticator), ``passkey`` (a passkey usable for this person; on a
native sign-in too since decision 361, scoped to the attested app), ``recovery`` (unused
recovery codes), or for
an unusual-sign-in check ``email_code`` alone. An unenrolled challenge offers nothing: the
person enrols first.
"""

from django.contrib.auth.hashers import check_password
from django.utils import timezone

from apps.accounts import audit_events
from apps.accounts.login_security_contract import (
    FACTOR_EMAIL_CODE, FACTOR_PASSKEY, FACTOR_RECOVERY, FACTOR_TOTP, MFA_METHOD_PASSKEY,
    MFA_METHOD_RECOVERY, MFA_METHOD_TOTP, PURPOSE_RISK,
)


def offered(user, row, context):
    from apps.accounts.mfa_policy import has_passkey, totp_enabled
    if (context or {}).get("purpose") == PURPOSE_RISK:
        return [FACTOR_EMAIL_CODE]
    factors = []
    if totp_enabled(user, row):
        factors.append(FACTOR_TOTP)
    if (context or {}).get("surface") != "control" and has_passkey(user):
        from apps.accounts.passkeys.native import device_passkey_factor_available
        from apps.accounts.passkeys.policy import passkeys_usable
        device = (context or {}).get("device")
        if passkeys_usable(user) and (not device or device_passkey_factor_available(context)):
            factors.append(FACTOR_PASSKEY)
    if totp_enabled(user, row) and row.recovery_digests:
        factors.append(FACTOR_RECOVERY)
    return factors


def _totp(row, code):
    from apps.accounts.mfa_crypto import matching_step
    from apps.makerspaces.secrets import decrypt_value
    if not row.secret:
        return False
    step = matching_step(decrypt_value(row.secret), code, timezone.now().timestamp(), row.last_step)
    if step is None:
        return False
    row.last_step = step
    row.save(update_fields=["last_step"])
    return True


def _recovery(row, code):
    for index, digest in enumerate(row.recovery_digests or []):
        if check_password(code, digest):
            row.recovery_digests = row.recovery_digests[:index] + row.recovery_digests[index + 1:]
            row.save(update_fields=["recovery_digests"])
            audit_events.record_auth_event(row.user, "auth.mfa_recovery_used", target=row.user)
            return True
    return False


def verify(user, row, challenge, request, *, factor, code, webauthn):
    """The method (``totp|recovery|passkey``) the answer proved, else None.

    No ``factor`` keeps the release-1 behaviour: an authenticator code, then a recovery
    code. A passkey answer goes through S-A's ``verify_mfa`` for this very challenge."""
    from apps.accounts.mfa_policy import totp_enabled
    if factor == FACTOR_PASSKEY:
        from apps.accounts.passkeys.assertion import verify_mfa
        from apps.accounts.passkeys.ceremonies import PasskeyFailed
        if not webauthn or FACTOR_PASSKEY not in offered(user, row, challenge.context):
            return None
        try:
            verify_mfa(challenge, webauthn["ceremony"], webauthn["credential"], request)
        except PasskeyFailed:
            return None
        return MFA_METHOD_PASSKEY
    if not code or not totp_enabled(user, row):
        return None
    if factor in (None, FACTOR_TOTP) and _totp(row, code):
        return MFA_METHOD_TOTP
    if factor in (None, FACTOR_RECOVERY) and _recovery(row, code):
        return MFA_METHOD_RECOVERY
    return None
