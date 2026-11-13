"""Passwordless passkey sign-in on a phone, ending in an attested device grant (358 B).

Two calls, like the web ceremony, but bound to device attestation like every other native
sign-in door:

1. ``begin_native_login``: an unspent approved attestation challenge (not consumed here)
   names the app; the RP ID is the deployment's public web domain and the expected origin
   is that attested app's (`native.native_scope`). Returns the WebAuthn request options.
2. ``finish_native_login``: the view has already consumed and verified the attestation for
   the SAME challenge; the ceremony is consumed against the origin recomputed from it, the
   assertion is verified by `ceremonies.verify_assertion` (the web code path), the person
   passes the web sign-in rules (`assertion._may_sign_in`: passkeys usable under both
   switches, account active, member accounts on or a staff role) and a MEMBER grant is
   issued with a VERIFIED ``mfa_method=passkey`` session, exactly what a web passkey
   sign-in yields. Staff authority is a later step-up (``auth/device/staff-grant``).
"""

from django.utils.translation import gettext
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.attestation import live_approved_challenge
from apps.accounts.login_security_contract import CEREMONY_LOGIN, MFA_METHOD_PASSKEY
from apps.accounts.passkeys import ceremonies
from apps.accounts.passkeys.ceremonies import PasskeyFailed
from apps.accounts.passkeys.native import native_scope
from apps.accounts.passkeys.policy import PasskeysUnavailable
from apps.audit import services as audit

LOGIN_METHOD = "passkey"


class NativePasskeyRetryRequired(Exception):
    """The one-time challenge and ceremony were spent before the grant could be issued."""


def _invalid():
    return AuthenticationFailed(gettext("Invalid device credentials or attestation."))


def begin_native_login(*, platform, app_id, environment, challenge):
    from apps.accounts.login_methods import passkeys_enabled
    if not passkeys_enabled():
        raise PasskeysUnavailable(gettext("Passkeys are turned off on this deployment."))
    row = live_approved_challenge(challenge)
    if row is None or (row.platform, row.app_id, row.environment) != (platform, app_id, environment):
        raise _invalid()
    origin, rp_id = native_scope(row)
    return ceremonies.assertion_options(CEREMONY_LOGIN, origin=origin, rp_id=rp_id)


def finish_native_login(request, *, ceremony_id, credential, challenge, verified):
    """``challenge`` is the consumed, attestation-verified challenge row."""
    from apps.accounts.models import User
    from apps.accounts.models_mfa import UserMFA
    from apps.accounts.mfa_policy import stamp
    from apps.accounts.passkeys.assertion import _may_sign_in, _owner
    from apps.accounts.services_device_grants import (
        DeviceGrantCreationRetryRequired, issue_first_device_session,
    )
    from apps.accounts.services_device_tokens import assert_mobile_grant_creation_enabled
    origin, _rp_id = native_scope(challenge)
    ceremony = ceremonies.consume(ceremony_id, CEREMONY_LOGIN, origin=origin)
    failure = None
    try:
        row = ceremonies.verify_assertion(ceremony, credential)
        user = User.objects.get(pk=row.user_id)
        if not _may_sign_in(user):
            raise PasskeyFailed()
    except PasskeyFailed as exc:
        failure = exc
    if failure is not None:
        owner = _owner(credential)
        audit.record(owner, "auth.passkey_login_failed", target=owner)
        raise failure
    assert_mobile_grant_creation_enabled()
    mfa, _ = UserMFA.objects.get_or_create(user=user)
    stamp(user, mfa, MFA_METHOD_PASSKEY)  # carried through the issuance lock onto the token claims
    try:
        access, refresh, grant = issue_first_device_session(user, challenge, verified, login_method=LOGIN_METHOD)
    except DeviceGrantCreationRetryRequired as exc:
        raise NativePasskeyRetryRequired from exc
    audit.record(user, "auth.passkey_login_succeeded", target=user)
    request.device_grant = grant
    return user, access, refresh, grant
