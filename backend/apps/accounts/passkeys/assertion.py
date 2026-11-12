"""Using a passkey: passwordless sign-in, a second factor, re-authentication, a proof.

- Sign-in (``begin_login``/``finish_login``): discoverable credentials and conditional UI,
  user verification required, so the session is VERIFIED with ``mfa_method=passkey``.
- Second factor (``begin_mfa``/``verify_mfa``): after a password, for an MFA challenge
  the login door started. S-B's ``mfa_challenges._finish`` calls ``verify_mfa`` for the
  ``passkey`` factor and stamps ``mfa_policy.stamp(user, row, "passkey")``.
- Re-authentication (``begin_reauth``/``finish_reauth``): a fresh passkey is a full
  step-up (possession plus user verification) for the ten-minute window; a phone session
  uses it too (358 B), scoped by `native.ceremony_scope`.
- Native passwordless sign-in lives in `native_login.py` and reuses ``_may_sign_in`` and
  ``ceremonies.verify_assertion``.
- Proof of another account (``begin_proof``/``verify_proof``): U-C's account-merge
  ``credentials`` method may accept the SOURCE account's passkey instead of its TOTP.

Only credentials registered on the request's RP ID are offered or accepted.
"""

from django.utils.translation import gettext
from django.db import transaction

from apps.accounts.login_security_contract import (
    CEREMONY_LOGIN, CEREMONY_MFA, CEREMONY_REAUTH, MFA_METHOD_PASSKEY,
)
from apps.accounts.passkeys import ceremonies
from apps.accounts.passkeys.ceremonies import PasskeyFailed
from apps.accounts.passkeys.policy import PasskeysUnavailable, assert_usable, passkeys_usable
from apps.accounts.passkeys.rp_id import normalize_origin, request_origin_and_rp_id
from apps.audit import services as audit


def _owner(credential):
    from apps.accounts.models_webauthn import WebAuthnCredential
    row = WebAuthnCredential.objects.filter(credential_id=ceremonies._credential_id(credential)).select_related(
        "user").first() if isinstance(credential, dict) else None
    return row.user if row is not None else None


def begin_login(request):
    from apps.accounts.login_methods import passkeys_enabled
    origin, rp_id = request_origin_and_rp_id(request)
    if not passkeys_enabled():
        raise PasskeysUnavailable(gettext("Passkeys are turned off on this deployment."))
    return ceremonies.assertion_options(CEREMONY_LOGIN, origin=origin, rp_id=rp_id)


def _may_sign_in(user):
    from apps.accounts.member_identity import member_accounts_enabled
    from apps.accounts.services_mfa import active
    from apps.accounts.staff_identity import has_staff_role, is_person
    if not is_person(user) or not passkeys_usable(user):
        return False
    try:
        active(user)
    except Exception:
        return False
    # Staff are never locked out by the member-account switch (#162(1)).
    return member_accounts_enabled() or has_staff_role(user)


def finish_login(request, ceremony_id, credential):
    from apps.accounts.mfa_policy import stamp
    from apps.accounts.models import User
    from apps.accounts.models_mfa import UserMFA
    from apps.accounts.passkeys.services import browser_session
    origin, _rp_id = request_origin_and_rp_id(request)
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
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user.pk)
        mfa, _ = UserMFA.objects.get_or_create(user=user)
        stamp(user, mfa, MFA_METHOD_PASSKEY)
        surface = ("verification_only" if user.self_registered_at is not None and user.email_verified_at is None
                   else "member")
        session = browser_session(user, request, surface)
        audit.record(user, "auth.passkey_login_succeeded", target=user)
    return session


def _live_challenge(raw):
    from django.conf import settings
    from django.utils import timezone

    from apps.accounts.mfa_challenges import digest
    from apps.accounts.models_mfa import MFAChallenge
    challenge = MFAChallenge.objects.select_related("user").filter(token_digest=digest(raw)).first()
    if (challenge is None or challenge.consumed_at is not None or challenge.expires_at <= timezone.now()
            or challenge.attempts >= settings.MFA_MAX_ATTEMPTS):
        raise PasskeyFailed(gettext("This sign-in expired. Start again."))
    return challenge


def begin_mfa(request, raw_challenge):
    """Options for the second factor of one pending MFA challenge (never consumed here).

    A device challenge (a native password sign-in, 361 item 4) is scoped to its attested app
    (`native.mfa_ceremony_scope`); a browser challenge must come from the origin it started on.
    """
    from apps.accounts.passkeys.native import mfa_ceremony_scope, mfa_device_identity
    from apps.accounts.staff_identity import is_person
    challenge = _live_challenge(raw_challenge)
    context = challenge.context or {}
    device = bool(context.get("device"))
    origin, rp_id = mfa_ceremony_scope(context, request)
    if ((not device and context.get("origin", "") != origin) or context.get("surface") == "control"
            or (device and mfa_device_identity(context) is None) or not is_person(challenge.user)):
        raise PasskeyFailed()
    assert_usable(challenge.user)
    return ceremonies.assertion_options(CEREMONY_MFA, origin=origin, rp_id=rp_id, user=challenge.user,
                                        mfa_challenge=challenge)


def verify_mfa(challenge, ceremony_id, credential, request):
    """For S-B's ``mfa_challenges._finish``: ``challenge`` is the locked ``MFAChallenge``.
    Returns the verified ``WebAuthnCredential``; raises ``PasskeyFailed`` otherwise."""
    from apps.accounts.passkeys.native import mfa_ceremony_scope
    from apps.accounts.passkeys.rp_id import RpIdUnavailable
    try:
        origin = (mfa_ceremony_scope(challenge.context, request)[0] if (challenge.context or {}).get("device")
                  else normalize_origin(request.headers.get("Origin", "")))
    except RpIdUnavailable as exc:
        raise PasskeyFailed() from exc
    ceremony = ceremonies.consume(ceremony_id, CEREMONY_MFA, origin=origin)
    if ceremony.mfa_challenge_id != challenge.pk or not passkeys_usable(challenge.user):
        raise PasskeyFailed()
    return ceremonies.verify_assertion(ceremony, credential, user=challenge.user)


def begin_reauth(request):
    from apps.accounts.passkeys.native import assert_person_session, ceremony_scope
    user = assert_person_session(request)
    assert_usable(user)
    origin, rp_id = ceremony_scope(request)
    return ceremonies.assertion_options(CEREMONY_REAUTH, origin=origin, rp_id=rp_id, user=user)


def finish_reauth(request, ceremony_id, credential):
    from apps.accounts import audit_events, reauthentication
    from apps.accounts.passkeys.native import assert_person_session, ceremony_scope
    user = assert_person_session(request)
    origin, _rp_id = ceremony_scope(request)
    ceremony = ceremonies.consume(ceremony_id, CEREMONY_REAUTH, origin=origin)
    try:
        if ceremony.user_id != user.pk or not passkeys_usable(user):
            raise PasskeyFailed()
        ceremonies.verify_assertion(ceremony, credential, user=user)
    except PasskeyFailed:
        audit_events.record_auth_event(user, "auth.reauthentication_failed", target=user)
        raise
    with transaction.atomic():
        reauthentication.stamp(request)
    return {"verified": True, "expires_in": int(reauthentication.WINDOW.total_seconds())}


def begin_proof(request, account):
    """Options proving ``account`` (not the signed-in person) holds a passkey on this RP
    ID. Call it only after the account's password matched, so the offered credential
    list never answers "does this account exist"."""
    origin, rp_id = request_origin_and_rp_id(request)
    assert_usable(account)
    return ceremonies.assertion_options(CEREMONY_REAUTH, origin=origin, rp_id=rp_id, user=account)


def verify_proof(request, account, ceremony_id, credential):
    """True when ``account``'s passkey answered ``begin_proof``'s ceremony; never raises
    for a wrong passkey, so the caller counts and audits the failure itself."""
    origin = normalize_origin(request.headers.get("Origin", ""))
    try:
        ceremony = ceremonies.consume(ceremony_id, CEREMONY_REAUTH, origin=origin)
        if ceremony.user_id != account.pk or not passkeys_usable(account):
            return False
        ceremonies.verify_assertion(ceremony, credential, user=account)
    except PasskeyFailed:
        return False
    return True
