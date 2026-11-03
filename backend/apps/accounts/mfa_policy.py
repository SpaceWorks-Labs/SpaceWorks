"""The same MFA floor for browser, native, refresh, and Django sessions.

Staff MFA is mandatory (#62): every person with elevated authority (a staff role,
organization authority or a resource grant) must hold a second factor, whatever the
platform ``mfa_enabled`` switch says; that switch governs member opt-in only. The
superadmin is exempt (``/control/`` keeps its own step-up). A factor is an enabled
authenticator (TOTP) or at least one passkey (#74: offered, never forced).

Where the floor bites:
- an ENROLLED account proves its factor at every sign-in (``needs_challenge``) and every
  token carries that proof (``assert_verified``);
- an elevated person WITHOUT a factor still signs in -- member features are never blocked
  (#128 C-1) -- but staff routes refuse them once their 3-day grace has ended
  (``staff_identity.require_staff_mfa`` and ``mfa_grace``).
"""

from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from apps.accounts.login_methods import mfa_login_enabled
from apps.accounts.login_security_contract import (
    MFA_METHOD_CLAIM, MFA_METHOD_PASSKEY, MFA_METHOD_TOTP, MFA_METHODS, MFA_SOURCE_EMAIL_CODE,
)
from apps.accounts.models_mfa import UserMFA

VERIFIED = "verified"
PROVIDER = "provider"
NONE = "none"
BYPASS = "bypass"
EMAIL_CODE = MFA_SOURCE_EMAIL_CODE
_PROOF_ATTRS = ("_mfa_verified_version", "_mfa_provider_verified", "_mfa_source", "_mfa_method")


def _is_superadmin(user):
    return bool(getattr(user, "is_superuser", False) or getattr(user, "role", None) == "superadmin")


def required(user):
    """Every non-superadmin person holding elevated authority, independent of the
    platform switch and of whether they have enrolled yet."""
    if user is None or getattr(user, "pk", None) is None or _is_superadmin(user):
        return False
    from apps.accounts.staff_identity import has_elevated_authority
    return has_elevated_authority(user)


def available(user=None):
    """Two-step sign-in is offered: the platform switch, or mandatory for this person."""
    return mfa_login_enabled() or (user is not None and required(user))


def assert_available(user=None):
    if not available(user):
        raise PermissionDenied("Two-step sign-in is turned off on this deployment.")


def credential(user):
    return UserMFA.objects.filter(user=user).first()


def totp_enabled(user, row=None):
    row = row if row is not None else credential(user)
    return bool(row and row.enabled_at)


def has_passkey(user):
    from apps.accounts.models_webauthn import WebAuthnCredential
    return WebAuthnCredential.objects.filter(user_id=user.pk).exists()


def is_enrolled(user, row=None):
    """An enabled authenticator OR at least one passkey. A passkey whose relying-party
    ID this deployment no longer serves still counts: a domain change never downgrades
    an account to "no factor"."""
    if getattr(user, "pk", None) is None:
        return False
    return totp_enabled(user, row) or has_passkey(user)


def staff_factor_enrolled(user):
    """Enrolled for STAFF purposes: a passkey counts only while passkeys are usable for
    this person (``security.passkeys_allowed`` across their staff spaces)."""
    if totp_enabled(user):
        return True
    from apps.accounts.passkeys.policy import passkeys_usable
    return has_passkey(user) and passkeys_usable(user)


def needs_challenge(user):
    """An enrolled account proves its factor at every sign-in while MFA applies to it."""
    return available(user) and is_enrolled(user)


def source_for(user):
    """Describe the proof actually presented, never infer TOTP proof from enrollment."""
    if getattr(user, "_mfa_verified_version", None) is not None:
        return VERIFIED
    if getattr(user, "_mfa_provider_verified", False):
        return PROVIDER
    if getattr(user, "_mfa_source", None) in (BYPASS, EMAIL_CODE):
        return user._mfa_source
    # BYPASS marks "MFA paused by the switch" so switching it back on revokes the session.
    # It never applies to a required person: the switch does not govern staff MFA.
    if not mfa_login_enabled() and not required(user) and totp_enabled(user):
        return BYPASS
    return NONE


def method_for(user):
    """Which factor produced VERIFIED proof (``totp|recovery|passkey``), else None."""
    method = getattr(user, "_mfa_method", None)
    return method if source_for(user) == VERIFIED and method in MFA_METHODS else None


def restore_proof(user, claims):
    """Carry only the presented refresh token's proof into a replacement token."""
    for attr in _PROOF_ATTRS:
        user.__dict__.pop(attr, None)
    source = claims.get("mfa_source")
    if source in (VERIFIED, None) and claims.get("mfa_version"):
        user._mfa_verified_version = str(claims["mfa_version"])
        if claims.get(MFA_METHOD_CLAIM) in MFA_METHODS:
            user._mfa_method = claims[MFA_METHOD_CLAIM]
    elif source == PROVIDER:
        user._mfa_provider_verified = True
    elif source in (BYPASS, EMAIL_CODE):
        user._mfa_source = source


def stamp_claims(user, token):
    """Write the proof claims of a freshly minted or rotated token."""
    token["mfa_source"] = source_for(user)
    row = credential(user)
    if row:
        token["mfa_version"] = str(row.version)
    method = method_for(user)
    if method:
        token[MFA_METHOD_CLAIM] = method
    else:
        token.payload.pop(MFA_METHOD_CLAIM, None)


def _mismatch():
    return AuthenticationFailed("Sign in again and verify MFA.", code="mfa_required")


def assert_verified(user, claims=None):
    """The proof floor for every token and control session.

    An enrolled account needs VERIFIED proof for its current factor version. Provider
    proof stands in only for people MFA is not mandatory for; an emailed code (S-B's
    unusual-login check) never does. An elevated person without any factor still gets a
    session: staff routes enforce enrolment (``require_staff_mfa``), member routes never.
    """
    row = credential(user)
    # Checked even with the switch off: a credential reset or disable bumps the version,
    # and that must still revoke every session minted against the old one.
    if row and claims is not None and str(claims.get("mfa_version") or "") != str(row.version):
        raise _mismatch()
    if not available(user):
        return
    source = claims.get("mfa_source") if claims is not None else source_for(user)
    enrolled = is_enrolled(user, row)
    if source == BYPASS:
        if enrolled:
            raise _mismatch()
        raise AuthenticationFailed("Enroll in MFA before continuing.", code="mfa_enrollment_required")
    if source == PROVIDER and not required(user):
        return
    if not enrolled:
        return
    # An enrolled account needs proof, not just a matching version: a "none" token can
    # be minted if the switch flips on between issuance's policy check and its stamp.
    # A missing source is a legacy token, which predates sources and was verified.
    if claims is not None and source not in (None, VERIFIED):
        raise _mismatch()
    version = claims.get("mfa_version") if claims is not None else getattr(user, "_mfa_verified_version", None)
    if row is None or str(version or "") != str(row.version):
        raise _mismatch()


def verified_staff_proof(user, claims):
    """True when the presented proof satisfies staff MFA: VERIFIED by one of the known
    factors and bound to the live factor version. Provider, emailed-code, none and
    bypass proof never do."""
    if claims is not None:
        source, version, method = claims.get("mfa_source"), claims.get("mfa_version"), claims.get(MFA_METHOD_CLAIM)
    else:
        source, version, method = source_for(user), getattr(user, "_mfa_verified_version", None), method_for(user)
    if source != VERIFIED or method not in MFA_METHODS or not version:
        return False
    row = credential(user)
    if row is None or str(version) != str(row.version):
        return False
    if method == MFA_METHOD_PASSKEY:
        from apps.accounts.passkeys.policy import passkeys_usable
        return passkeys_usable(user)
    return True


def stamp(user, row, method=MFA_METHOD_TOTP):
    """Mark ``user`` as having proved ``method`` against ``row``'s current version."""
    user._mfa_verified_version = str(row.version)
    user._mfa_method = method if method in MFA_METHODS else MFA_METHOD_TOTP
