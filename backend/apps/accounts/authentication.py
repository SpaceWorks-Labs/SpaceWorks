import re

from rest_framework.exceptions import AuthenticationFailed
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError

from apps.accounts.claim_route_types import AnonymousRead, ControlRoute, Refused
from apps.accounts.claim_routes import policy_for
from apps.accounts.claim_sessions import (
    ClaimSessionInvalid,
    attach_claim_context,
    validated_claim_session,
)
from apps.accounts.claim_tenants import claim_tenant_matches
from apps.accounts.claim_tokens import ClaimAccessToken
from apps.accounts.claim_routes import CLAIM_REACHABLE_PREFIXES
from apps.accounts.models import User
from apps.accounts.authentication_device import heartbeat_device_grant, validated_device_grant
from apps.accounts.tokens import validate_auth_generation


VERIFICATION_ONLY_SURFACE = "verification_only"
# Account-split cutover rejects the pre-kind and surface-less token generations.
TREAT_MISSING_SURFACE_AS_MEMBER_FOR_ONE_RELEASE = False
# One account per person (release 2): a person's session is `member` (or
# `verification_only`) whatever staff roles they hold -- staff routes are admitted per
# request by surface_policy -- and the superadmin's is `platform`. The release-1
# `staff`, `staff_api` and `delegated` surfaces are gone with the staff account kind.
_KNOWN_SESSION_SURFACES = {"member", "platform", VERIFICATION_ONLY_SURFACE}


class SpaceWorksJWTAuthentication(JWTAuthentication):
    """Adds immediate device-grant checks while preserving ordinary JWT behavior."""

    def authenticate(self, request):
        claim_authenticated = self._authenticate_claim(request)
        if claim_authenticated is not False:
            return claim_authenticated
        authenticated = super().authenticate(request)
        if authenticated is None:
            return None
        user, token = authenticated
        if user.is_tenant_dump_stub or user.deletion_requested_at is not None:
            raise AuthenticationFailed("Account is not available.")
        validate_auth_generation(token)
        from apps.accounts.session_issuance import validate_session_generation
        validate_session_generation(user, token)
        # Set before route policy runs: native members cannot use organization
        # grants/governance to enter delegated staff routes, and the route gate needs the
        # grant's authority (a staff grant is a step-up fixed to one makerspace).
        grant = None
        if token.get("device_grant_id"):
            from apps.accounts.native_session import mark_native_session
            user.native_device_session = True
            mark_native_session(user)
            if not token.get("device_family_id"):
                raise AuthenticationFailed("Invalid device authorization.")
            grant = validated_device_grant(user, token)
            # #162(2): a member grant carries no staff authority, a staff grant only its tenant's.
            from apps.accounts.session_authority import limit_staff_authority
            limit_staff_authority(user, [grant.staff_makerspace_id] if grant.authority == "staff" else ())
        from apps.accounts.surface_policy import enforce_request
        enforce_request(user, token, request, grant=grant)
        from apps.accounts.mfa_policy import assert_verified
        assert_verified(user, token)
        from apps.backup.recovery import assert_principal_allowed

        assert_principal_allowed(user)
        surface = _effective_session_surface(token)
        if user.self_registered_at is not None and user.email_verified_at is None:
            # Enforce provenance at authentication too: an older device/phone issuer
            # cannot bypass verification merely because its token says member.
            surface = VERIFICATION_ONLY_SURFACE
        elif surface == VERIFICATION_ONLY_SURFACE:
            # Confirmation updates the user row, so the same already-issued session
            # becomes an ordinary member session immediately after ownership is proven.
            surface = "member"
        if surface == VERIFICATION_ONLY_SURFACE and not _verification_path_allowed(
            request.path
        ):
            raise PermissionDenied(
                "Verify the account email before accessing member APIs."
            )
        if grant is None:
            from apps.accounts.web_sessions import validate_session
            validate_session(user, token)
            if request.headers.get("X-Makerspace-Id") is not None:
                raise PermissionDenied("Native makerspace selection requires a device grant.")
            _assert_source_gate(request)
            request.session_authority = surface
            return authenticated
        staff = grant.authority == "staff"
        if staff and token.get("mfa_source") != "verified":
            raise AuthenticationFailed("Native staff sessions require MFA.")
        request.device_grant = grant
        request.native_app_registration = grant.registration
        from apps.makerspaces.origin_scope import validate_native_makerspace_scope

        from apps.accounts.delegated_routes import DELEGABLE, MEMBERSHIP_ONLY, route_class
        staff_route = route_class(getattr(request.resolver_match, "url_name", None)) in {DELEGABLE, MEMBERSHIP_ONLY}
        if staff and staff_route and request.headers.get("X-Makerspace-Id") is None:
            raise PermissionDenied("Native staff APIs require X-Makerspace-Id.")
        selected = validate_native_makerspace_scope(request, user, grant)
        if staff and selected is not None:
            kwargs = getattr(request.resolver_match, "kwargs", {}) or {}
            for key in ("makerspace_id", "makerspace_pk"):
                if key in kwargs and str(kwargs[key]) != str(selected):
                    raise PermissionDenied("Makerspace target does not match the selected makerspace.")
        _assert_source_gate(request)
        grant = heartbeat_device_grant(user, token)
        request.device_grant = grant
        from apps.accounts.device_activity import record_device_activity
        record_device_activity(grant, getattr(request, "selected_makerspace_membership", None))
        request.session_authority = "native_staff" if staff else surface
        return user, token

    def _authenticate_claim(self, request):
        header = self.get_header(request)
        if header is None:
            return False
        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return False
        try:
            token = ClaimAccessToken(raw_token)
        except TokenError:
            return False
        validate_auth_generation(token)

        view_name = getattr(request.resolver_match, "view_name", "") or ""
        policy = policy_for(view_name, request.method)
        if isinstance(policy, AnonymousRead):
            return None
        try:
            claim = validated_claim_session(token)
        except ClaimSessionInvalid as exc:
            from apps.presence.services import expire_claim_presence

            expire_claim_presence(token.get("claim_session_id"))
            raise AuthenticationFailed("Claim session is no longer active.") from exc
        if isinstance(policy, Refused):
            raise PermissionDenied(policy.reason)
        if not isinstance(policy, ControlRoute) and not claim_tenant_matches(
            policy.tenant,
            claim_makerspace_id=claim.membership.makerspace_id,
            view_name=view_name,
            url_kwargs=getattr(request.resolver_match, "kwargs", {}) or {},
            body=request.data,
        ):
            raise PermissionDenied("Claim session is not valid for this makerspace.")
        user = attach_claim_context(claim.membership.user, claim)
        from apps.accounts.session_authority import limit_staff_authority
        limit_staff_authority(user)  # #162(2): a claim session never carries staff authority.
        if user.is_tenant_dump_stub or user.deletion_requested_at is not None:
            raise AuthenticationFailed("Claim identity is not available.")
        from apps.backup.recovery import assert_principal_allowed

        assert_principal_allowed(user)
        from apps.accounts.delegated_routes import DELEGABLE, MEMBERSHIP_ONLY, route_class
        if (route_class(getattr(request.resolver_match, "url_name", None)) in {DELEGABLE, MEMBERSHIP_ONLY}
                and not _member_surface_path_allowed(request.path)):
            # A claim session is a bounded walk-in session: it never carries staff authority.
            raise PermissionDenied("Claim sessions cannot use staff routes.")
        request.claim_session = claim
        request.session_authority = "member"
        request.selected_makerspace_id = claim.membership.makerspace_id
        _assert_source_gate(request)
        return user, token


# Preserve SimpleJWT's documented Bearer security scheme after replacing its
# authenticator with the device-grant-aware subclass above.
from drf_spectacular.contrib.rest_framework_simplejwt import (  # noqa: E402
    SimpleJWTScheme,
)


class SpaceWorksJWTScheme(SimpleJWTScheme):
    target_class = "apps.accounts.authentication.SpaceWorksJWTAuthentication"

    def get_security_definition(self, auto_schema):
        return {
            **super().get_security_definition(auto_schema),
            "description": (
                "One account per person: a person's token reaches staff routes only "
                "where they hold a staff role (in every targeted makerspace), with "
                "staff MFA. Native member grants never carry staff authority; a native "
                "staff grant is fixed to one makerspace and its staff routes require a "
                "matching X-Makerspace-Id. Member APIs may omit the header. Personal "
                "notification inbox, preferences and announcements accept member "
                "sessions; broadcasts and the makerspace-wide feed need staff authority."
            ),
        }


# An ordinary member session is BROADER than a bounded claim session, so it needs its own
# allowlist rather than borrowing the claim prefixes. Reusing CLAIM_REACHABLE_PREFIXES was
# invisible while only social member logins carried this surface; once every member
# password login carries it, a legitimate member-owned action outside those prefixes --
# registering a phone for push -- starts 403ing. Anything added here must be an action the
# member performs on their OWN records; staff APIs never belong.
MEMBER_SURFACE_PREFIXES = CLAIM_REACHABLE_PREFIXES + (
    "/api/v1/integrations/push/", "/api/v1/notifications/inbox/",
    "/api/v1/notifications/preferences/", "/api/v1/notifications/announcements/",
)
PERSONAL_NOTIFICATION_PATH = re.compile(
    r"/api/v1/integrations/makerspace/[0-9]+/personal/"
    r"(?:endpoints(?:/start|/[0-9]+)?|challenges/[0-9]+/verify|preferences|deliveries)/?"
)


def _member_surface_path_allowed(path):
    # Accepting one's own invitation precedes staff access. Keep these exact paths:
    # listing, creating and revoking invitations still require a staff session.
    return path.rstrip("/") in {
        "/api/v1/me/messaging",
        "/api/v1/me/messaging/consent",
        "/api/v1/admin/event-staff-invites/redeem",
        "/api/v1/admin/booking-staff-invites/redeem",
    } or bool(PERSONAL_NOTIFICATION_PATH.fullmatch(path)) or path.startswith(MEMBER_SURFACE_PREFIXES)


def _verification_path_allowed(path):
    return path.rstrip("/") in {
        "/api/v1/auth/me",
        "/api/v1/auth/logout-all",
        "/api/v1/auth/email-verification/resend",
        "/api/v1/auth/email-verification/confirm",
    }


def _effective_session_surface(token):
    surface = token.get("surface")
    if surface is None and TREAT_MISSING_SURFACE_AS_MEMBER_FOR_ONE_RELEASE:
        return "member"
    if surface not in _KNOWN_SESSION_SURFACES:
        raise AuthenticationFailed("Invalid session surface.")
    return surface


def _assert_source_gate(request):
    from apps.tenant_migration.gate_runtime import assert_request_write_allowed

    assert_request_write_allowed(request)
