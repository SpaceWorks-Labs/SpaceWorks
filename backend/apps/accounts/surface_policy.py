"""Live account/surface boundary. Route services still decide individual actions."""

from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from apps.accounts.delegated_routes import (
    DELEGABLE, MEMBER_ONLY, MEMBERSHIP_ONLY, SHARED_ACCOUNT_UTILITY, SIGNED_PROTOCOL,
    route_class,
)
from apps.accounts.delegated_route_catalog import PLATFORM_ONLY_ROUTES
from apps.accounts.staff_identity import has_staff_role, is_person, is_platform, require_staff_mfa


PLATFORM_ROUTES = frozenset("""
backup-recovery-state
admin-module-groups admin-module-install admin-module-uninstall admin-space-pack-profiles
admin-makerspace-provision-subdomain user-restrict user-restore-access
admin-organization-list admin-organization-detail admin-organization-links admin-organization-email-sender
admin-organization-link-delete admin-organization-memberships admin-organization-membership-detail
admin-organization-invitations admin-organization-invitation-revoke
tenant-migration-disclosure-closure tenant-migration-disclosure-approvals
tenant-migration-disclosure-revoke tenant-migration-exports tenant-migration-export-detail
tenant-migration-export-download-url tenant-migration-source-quiesce
tenant-migration-source-archive tenant-migration-source-recover
admin-makerspaces admin-makerspace admin-platform-dashboard admin-platform-email-settings
admin-platform-payment-settings admin-platform-social-auth-settings admin-platform-problems
admin-platform-backup-settings admin-deployment-backups admin-backup-destinations
admin-backup-destination admin-backup-destination-probe admin-backup-destination-push
admin-backup-destination-retire admin-backup-destination-uploads admin-backup-archive-rehydrate
admin-restore-operations admin-restore-operation admin-restore-decision
tenant-migration-deployment-identity
tenant-migration-pairings tenant-migration-imports tenant-migration-import-upload-start
tenant-migration-import-archive-chunk tenant-migration-import-archive-complete
tenant-migration-import-detail tenant-migration-import-decisions tenant-migration-import-run
tenant-migration-import-verification tenant-migration-target-activate tenant-migration-target-abort
admin-backup-download-url admin-makerspace-backups
""".split())
PLATFORM_ROUTES |= PLATFORM_ONLY_ROUTES
from apps.accounts.security_route_catalog import ROUTES as SECURITY_ROUTES  # noqa: E402
PLATFORM_ROUTES |= SECURITY_ROUTES


PERSON_KIND = "person"
PLATFORM_KIND = "platform"
_SURFACES = {
    PERSON_KIND: frozenset({"member", "verification_only"}),
    PLATFORM_KIND: frozenset({"platform", "control"}),
}


def token_kind(user):
    """The token ``kind`` claim: ``person`` or ``platform``. An inert shell has none."""
    if is_person(user):
        return PERSON_KIND
    return PLATFORM_KIND if is_platform(user) else None


def _active(user):
    if (not user.is_active or user.retired_at is not None or user.is_tenant_dump_stub
            or user.access_status != "active" or getattr(user, "merged_into_id", None) is not None):
        raise AuthenticationFailed("Account is not available.")


def assert_surface(user, surface, request=None):
    _active(user)
    if surface not in _SURFACES.get(token_kind(user), ()):
        raise AuthenticationFailed("Invalid account context.")
    if surface == "platform" and request is not None:
        from django.conf import settings
        from apps.accounts.social_nonces import request_origin
        if request_origin(request) not in settings.PLATFORM_STAFF_ORIGINS:
            raise AuthenticationFailed("Invalid account context.")


def validate_account_token(user, token):
    """A token (or MFA challenge context) is bound to the kind it was minted for and
    never names a makerspace: staff authority is resolved per request, not carried."""
    _active(user)
    if token.get("kind") != token_kind(user) or token.get("makerspace") is not None:
        raise AuthenticationFailed("Invalid account context.")
    assert_surface(user, token.get("surface"))


def _platform_route(name):
    return name in PLATFORM_ROUTES or bool(name and name.startswith("admin-staff-account"))


def _delegated(user, targets, name, *, native=False):
    from apps.accounts.native_session import is_native_session
    native = native or is_native_session(user)
    if native:
        return False
    from apps.accounts.rbac_organizations import _org_actions_for, has_any_org_authority
    from apps.makerspaces.resource_grant_sources import has_authority
    # Organization governance routes have no tenant of their own. Their views check
    # the particular organization; a grant in one organization cannot authorize another.
    if name and (name.startswith("admin-organization") or name == "organization-analytics"):
        if native:
            return False
        from apps.organizations.governance import has_any_governance
        if has_any_governance(user):
            return True
    if targets:
        return all((not native and _org_actions_for(user, target))
                   or has_authority(user, makerspace_ids=[target])
                   for target in targets)
    return (not native and has_any_org_authority(user)) or has_authority(user)


# Native member sessions never use these, even though their classes would admit a person.
_NATIVE_MEMBER_REFUSED = frozenset({
    "auth-organization-invitation-redeem", "auth-organizations-self-service",
    "booking-staff-invite-redeem",
})  # #173: a native member grant may redeem an event staff invite (it then steps up natively).
_STAFF_CLASSES = frozenset({MEMBERSHIP_ONLY, DELEGABLE})


def _staff_admits(user, token, request, targets, *, grant):
    """A person's staff role admits a membership-only or delegable route when it covers
    EVERY target (any servable space for a target-less route), under staff MFA.

    A verified custom origin pins the targets to its space; a native staff grant pins them
    to its fixed tenant. Native member grants and claim sessions never reach here.
    """
    from apps.makerspaces.origin_scope import (
        AMBIGUOUS_STAFF_ORIGIN_SCOPE, NO_STAFF_ORIGIN_SCOPE, staff_origin_scope,
    )
    scope = staff_origin_scope(request)
    if scope is AMBIGUOUS_STAFF_ORIGIN_SCOPE:
        raise PermissionDenied("Staff origin is ambiguous.")
    pins = [] if scope is NO_STAFF_ORIGIN_SCOPE else [scope]
    if grant is not None:
        pins.append(grant.staff_makerspace_id)
    for pin in pins:
        if targets - {pin}:
            raise PermissionDenied("Account context does not match this makerspace.")
        targets = {pin}
    if not (all(has_staff_role(user, target) for target in targets) if targets else has_staff_role(user)):
        return False
    from apps.accounts.staff_network import assert_staff_network  # per-space staff IP allow-list (S-C)
    assert_staff_network(request, user, targets)
    require_staff_mfa(user, token, route=getattr(getattr(request, "resolver_match", None), "url_name", None))
    if len(targets) == 1 and getattr(request, "selected_makerspace_id", None) is None:
        request.selected_makerspace_id = next(iter(targets))
    return True


def enforce_request(user, token, request, *, grant=None):
    """Route-class gate for one authenticated request. ``grant`` is the validated native
    device grant, when the token carries one."""
    validate_account_token(user, token)
    assert_surface(user, token.get("surface"), request)
    from apps.accounts.authentication import _member_surface_path_allowed
    from apps.makerspaces.origin_scope_routes import request_route_targets
    match = getattr(request, "resolver_match", None)
    name = getattr(match, "url_name", None)
    classification = route_class(name)
    from apps.accounts.native_session import is_native_session
    native = grant is not None or is_native_session(user) or bool(token.get("device_grant_id"))
    staff_grant = grant if native and getattr(grant, "authority", None) == "staff" else None
    if classification == SIGNED_PROTOCOL:
        raise PermissionDenied("Provider signature required.")
    _name, targets, invalid, _recognized = request_route_targets(request)
    if is_platform(user):
        # Owner decision #115: the superadmin also enters every Space-Manager route.
        from apps.accounts.platform_tenant_surface import admits
        if (classification != SHARED_ACCOUNT_UTILITY and not _platform_route(name)
                and not admits(user, request, classification, targets, invalid, native=native)):
            raise PermissionDenied("Platform account context is required.")
        return
    from apps.accounts.native_event_grants import admits_event_route
    if native and admits_event_route(user, token, request, name, grant):
        return  # #173: an event grant reaches its own event's programme routes and nothing staff.
    if native and staff_grant is None and (
        (classification == DELEGABLE and name != "payment-document-download") or name in _NATIVE_MEMBER_REFUSED
    ):
        raise PermissionDenied("Native member sessions cannot use delegated authority.")
    if classification == SHARED_ACCOUNT_UTILITY:
        return
    if classification == MEMBER_ONLY:
        if invalid:
            raise PermissionDenied("Invalid account scope.")
        return
    # This mixed-audience download revalidates its signed, user-bound grant and
    # own-charge/VIEW_FINANCE authority in the view, including on every retry.
    if name == "payment-document-download":
        if invalid:
            raise PermissionDenied("Invalid document scope.")
        return
    if classification is None and request.path.startswith("/api/v1/auth/"):
        raise PermissionDenied("Unknown account route.")
    if _member_surface_path_allowed(request.path):
        return
    if classification in _STAFF_CLASSES and not invalid:
        if (not native or staff_grant is not None) and _staff_admits(
                user, token, request, set(targets), grant=staff_grant):
            return
        if classification == DELEGABLE and _delegated(user, targets, name, native=native):
            # Organization and resource-grant authority is elevated authority too (#62).
            require_staff_mfa(user, token, route=name)
            return
        raise PermissionDenied("A staff role in this makerspace is required.")
    raise PermissionDenied("A delegated authority source is required.")
