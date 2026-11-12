"""Adding, renaming and removing a person's passkeys (web only, #66 / Q10).

Every change needs a recent re-authentication, runs under the User lock and, for an add
or a removal, bumps ``UserMFA.version`` and ends every session, exactly like an
authenticator change. The browser that made the change gets a fresh session carrying
the proof it still holds (a new passkey proves itself). Removing the last factor of a
person staff MFA is mandatory for is refused (``last_factor``).
"""

from django.utils.translation import gettext
import uuid

from django.db import transaction
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.accounts import security_signals
from apps.accounts.login_security_contract import (
    LAST_FACTOR, MFA_METHOD_PASSKEY, MFA_METHOD_RECOVERY, MFA_METHOD_TOTP,
)
from apps.accounts.models_webauthn import WebAuthnCredential
from apps.accounts.passkeys import ceremonies
from apps.accounts.passkeys.ceremonies import MAX_PASSKEYS, PasskeyFailed
from apps.accounts.passkeys.policy import assert_usable, passkeys_usable
from apps.accounts.passkeys.rp_id import request_origin_and_rp_id
from apps.audit import services as audit

_TRANSPORTS = frozenset({"usb", "nfc", "ble", "internal", "hybrid", "cable", "smart-card"})


def assert_web_person(request):
    """A person's own browser session: never a platform account, a native app or a
    verification-only session (passkeys are web-only in v1, Q10)."""
    from apps.accounts.native_session import is_native_session
    from apps.accounts.staff_identity import is_person
    user, token = request.user, getattr(request, "auth", None)
    if not is_person(user):
        raise PermissionDenied(gettext("Passkeys are for personal accounts."))
    if (getattr(request, "device_grant", None) is not None or is_native_session(user)
            or token is None or token.get("device_grant_id") or token.get("surface") != "member"):
        raise PermissionDenied(gettext("Manage passkeys from the website."))
    return user


def _gate(request):
    from apps.accounts.reauthentication import require_recent_reauth
    user = assert_web_person(request)
    require_recent_reauth(request)
    return user


def begin_registration(request):
    user = _gate(request)
    assert_usable(user)
    if WebAuthnCredential.objects.filter(user=user).count() >= MAX_PASSKEYS:
        raise PasskeyFailed(gettext("You can keep up to %(max)s passkeys. Remove one first.") % {"max": MAX_PASSKEYS})
    origin, rp_id = request_origin_and_rp_id(request)
    return ceremonies.registration_options(user, origin=origin, rp_id=rp_id)


def _transports(credential):
    response = credential.get("response") if isinstance(credential, dict) else None
    values = response.get("transports") if isinstance(response, dict) else None
    return sorted({value for value in values or () if value in _TRANSPORTS})


def browser_session(user, request, surface="member"):
    from apps.accounts.serializers_payload import user_payload
    from apps.accounts.tokens import SpaceWorksRefreshToken
    refresh = SpaceWorksRefreshToken.for_user(user)
    refresh["surface"] = surface
    return {"access": str(refresh.access_token), "refresh": str(refresh), "surface": surface,
            "user": user_payload(user, request=request, session_authority=surface)}


def _changed(user, mfa):
    from apps.accounts.services_tokens import blacklist_outstanding_tokens
    mfa.version = uuid.uuid4()
    mfa.save()
    blacklist_outstanding_tokens(user)


def finish_registration(request, ceremony_id, credential, name=""):
    from apps.accounts.mfa_crypto import recovery_codes
    from apps.accounts.mfa_grace import close_grace
    from apps.accounts.mfa_policy import stamp
    from apps.accounts.models import User
    from apps.accounts.models_mfa import UserMFA
    user = _gate(request)
    assert_usable(user)
    origin, _rp_id = request_origin_and_rp_id(request)
    ceremony = ceremonies.consume(ceremony_id, "registration", origin=origin)
    if ceremony.user_id != user.pk:
        raise PasskeyFailed()
    verified = ceremonies.verify_registration(ceremony, credential)
    credential_id = ceremonies.b64url(verified.credential_id)
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user.pk)
        if WebAuthnCredential.objects.filter(user=user).count() >= MAX_PASSKEYS:
            raise PasskeyFailed(gettext("You can keep up to %(max)s passkeys. Remove one first.") % {"max": MAX_PASSKEYS})
        if WebAuthnCredential.objects.filter(credential_id=credential_id).exists():
            raise PasskeyFailed(gettext("This passkey is already registered."))
        row = WebAuthnCredential.objects.create(
            user=user, credential_id=credential_id, public_key=verified.credential_public_key,
            sign_count=verified.sign_count, transports=_transports(credential), aaguid=str(verified.aaguid or ""),
            backed_up=verified.credential_backed_up, rp_id=ceremony.rp_id,
            name=(str(name or "").strip() or "Passkey")[:64])
        mfa, _ = UserMFA.objects.select_for_update().get_or_create(user=user)
        codes = None
        if not mfa.recovery_digests:
            codes, mfa.recovery_digests = recovery_codes()
        _changed(user, mfa)
        audit.record(user, "auth.passkey_registered", target=user)
        close_grace(user)
        security_signals.send_mfa_changed(user, security_signals.PASSKEY_ADDED)
        stamp(user, mfa, MFA_METHOD_PASSKEY)
        session = browser_session(user, request)
    return row, codes, session


def rename(request, pk, name):
    user = _gate(request)
    with transaction.atomic():
        row = WebAuthnCredential.objects.select_for_update().filter(pk=pk, user=user).first()
        if row is None:
            raise NotFound(gettext("Passkey not found."))
        row.name = (str(name or "").strip() or "Passkey")[:64]
        row.save(update_fields=["name"])
        audit.record(user, "auth.passkey_renamed", target=user)
    return row


def _reissue(user, request, mfa, method):
    """A fresh session for the browser that removed a passkey, carrying the proof it
    still holds; None when that proof is gone (the person signs in again)."""
    from apps.accounts.mfa_policy import is_enrolled, stamp, totp_enabled
    if not is_enrolled(user, mfa):
        return browser_session(user, request)
    still_valid = ((method in (MFA_METHOD_TOTP, MFA_METHOD_RECOVERY) and totp_enabled(user, mfa))
                   or (method == MFA_METHOD_PASSKEY and WebAuthnCredential.objects.filter(user=user).exists()))
    if not still_valid:
        return None
    stamp(user, mfa, method)
    return browser_session(user, request)


def remove(request, pk):
    from apps.accounts.mfa_policy import required, totp_enabled
    from apps.accounts.models import User
    from apps.accounts.models_mfa import UserMFA
    user = _gate(request)
    method = request.auth.get("mfa_method") if request.auth.get("mfa_source") == "verified" else None
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user.pk)
        row = WebAuthnCredential.objects.select_for_update().filter(pk=pk, user=user).first()
        if row is None:
            raise NotFound(gettext("Passkey not found."))
        mfa, _ = UserMFA.objects.select_for_update().get_or_create(user=user)
        others = WebAuthnCredential.objects.filter(user=user).exclude(pk=row.pk).exists()
        if required(user) and not totp_enabled(user, mfa) and not (others and passkeys_usable(user)):
            raise PermissionDenied({"detail": gettext("Staff need a second factor. Set up an authenticator or another "
                                              "passkey before removing this one."), "code": LAST_FACTOR})
        from apps.accounts.credential_inventory import would_strand
        if would_strand(user, drop_passkey_pk=row.pk):
            # A member who signs in only with passkeys would lock themselves out for good.
            raise PermissionDenied({"detail": gettext("This passkey is your only way to sign in. Add a password, "
                                                      "a sign-in provider or another passkey first."),
                                    "code": "last_credential"})
        row.delete()
        if not others and not totp_enabled(user, mfa):
            mfa.recovery_digests = []
        _changed(user, mfa)
        audit.record(user, "auth.passkey_removed", target=user)
        security_signals.send_mfa_changed(user, security_signals.PASSKEY_REMOVED)
        session = _reissue(user, request, mfa, method)
    return session
