"""The same MFA floor for browser, native, refresh, and Django sessions."""

from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from apps.accounts import rbac
from apps.accounts.models_mfa import UserMFA
from apps.accounts.login_methods import mfa_login_enabled
from apps.makerspaces.models import Makerspace
from apps.makerspaces.platform import feature_enabled


VERIFIED = "verified"
PROVIDER = "provider"
NONE = "none"
BYPASS = "bypass"


def available():
    return mfa_login_enabled()


def assert_available():
    if not available():
        raise PermissionDenied("Two-step sign-in is turned off on this deployment.")


def required(user):
    return available() and _required_when_available(user)


def _required_when_available(user):
    # Superadmin MFA is opt-in: an enrolled superadmin is still challenged through
    # needs_challenge(), and a lost authenticator is recovered on the host. Returned
    # explicitly because rbac grants superadmins every action in every space, so the
    # tenant `staff_mfa_required` check below would otherwise make it mandatory again.
    if user.is_superuser or user.role == "superadmin":
        return False
    # The common case (no tenant opted in) costs one scoped query, not one per action.
    candidates = Makerspace.objects.filter(enabled_features__contains=["security.staff_mfa_required"])
    local = rbac.scope_by_makerspace(user, candidates, "id")
    if any(rbac.effective_actions(user, space.pk) for space in local):
        return True
    from apps.makerspaces.resource_grant_sources import has_authority
    if has_authority(user, makerspace_ids=candidates.values_list("pk", flat=True)):
        return True
    if not rbac.has_any_org_authority(user):
        return False
    # Action-based scoping includes organization-derived staff, never community identity.
    for action in rbac.ROLE_GRANTABLE_ACTIONS:
        spaces = rbac.scope_by_action(user, action, candidates, "id")
        if any(feature_enabled(space, "security.staff_mfa_required") for space in spaces):
            return True
    return False


def credential(user):
    return UserMFA.objects.filter(user=user).first()


def needs_challenge(user):
    if not available():
        return False
    row = credential(user)
    return bool(row and row.enabled_at) or _required_when_available(user)


def source_for(user):
    """Describe the proof actually presented, never infer TOTP proof from enrollment."""
    if getattr(user, "_mfa_verified_version", None) is not None:
        return VERIFIED
    if getattr(user, "_mfa_provider_verified", False):
        return PROVIDER
    if getattr(user, "_mfa_source", None) == BYPASS:
        return BYPASS
    if not available():
        row = credential(user)
        if bool(row and row.enabled_at) or _required_when_available(user):
            return BYPASS
    return NONE


def restore_proof(user, claims):
    """Carry only the presented refresh token's proof into a replacement token."""
    for attr in ("_mfa_verified_version", "_mfa_provider_verified", "_mfa_source"):
        user.__dict__.pop(attr, None)
    source = claims.get("mfa_source")
    if source in (VERIFIED, None) and claims.get("mfa_version"):
        user._mfa_verified_version = str(claims["mfa_version"])
    elif source == PROVIDER:
        user._mfa_provider_verified = True
    elif source == BYPASS:
        user._mfa_source = BYPASS


def assert_verified(user, claims=None):
    # Shared by JWT authentication/issuance and the Django control-session bridge.
    row = credential(user)
    # Checked even with the switch off: a credential reset or disable bumps the version,
    # and that must still revoke every session minted against the old one.
    if row and claims is not None and str(claims.get("mfa_version") or "") != str(row.version):
        raise AuthenticationFailed("Sign in again and verify MFA.", code="mfa_required")
    if not available():
        return
    source = claims.get("mfa_source") if claims is not None else source_for(user)
    if source == BYPASS:
        if row and row.enabled_at:
            raise AuthenticationFailed("Sign in again and verify MFA.", code="mfa_required")
        raise AuthenticationFailed("Enroll in MFA before continuing.", code="mfa_enrollment_required")
    if source == PROVIDER:
        return
    if row and row.enabled_at:
        # An enrolled account needs proof, not just a matching version: a "none" token can
        # be minted if the switch flips on between issuance's policy check and its stamp.
        # A missing source is a legacy token, which predates sources and was verified.
        if claims is not None and source not in (None, VERIFIED):
            raise AuthenticationFailed("Sign in again and verify MFA.", code="mfa_required")
        version = (claims or {}).get("mfa_version") if claims is not None else getattr(
            user, "_mfa_verified_version", None
        )
        if str(version or "") != str(row.version):
            raise AuthenticationFailed("Sign in again and verify MFA.", code="mfa_required")
    elif required(user):
        raise AuthenticationFailed("Enroll in MFA before continuing.", code="mfa_enrollment_required")


def stamp(user, row):
    user._mfa_verified_version = str(row.version)
