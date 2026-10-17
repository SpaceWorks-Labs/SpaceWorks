"""Live account/surface boundary. Route services still decide individual actions."""

from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from apps.accounts.delegated_routes import DELEGABLE, SHARED_ACCOUNT_UTILITY, route_class


PLATFORM_ROUTES = frozenset("""
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
admin-backup-download-url
""".split())


def _active(user):
    if (not user.is_active or user.retired_at is not None or user.is_tenant_dump_stub
            or user.access_status != "active"):
        raise AuthenticationFailed("Account is not available.")


def assert_surface(user, surface, request=None):
    _active(user)
    allowed = {
        "member": {"member", "delegated", "verification_only"},
        "staff": {"staff", "staff_api"},
        "platform": {"platform", "control"},
    }
    if surface not in allowed.get(user.account_kind, set()):
        raise AuthenticationFailed("Invalid account context.")
    if surface == "platform" and request is not None:
        from django.conf import settings
        from apps.accounts.social_nonces import request_origin
        if request_origin(request) not in settings.PLATFORM_STAFF_ORIGINS:
            raise AuthenticationFailed("Invalid account context.")
    if user.account_kind == "staff":
        from apps.accounts import rbac
        if user.staff_makerspace_id not in rbac.resolve_scope(user):
            raise AuthenticationFailed("Account is not available.")
        if request is not None:
            from apps.makerspaces.origin_scope import (
                AMBIGUOUS_STAFF_ORIGIN_SCOPE, NO_STAFF_ORIGIN_SCOPE, staff_origin_scope,
            )
            scope = staff_origin_scope(request)
            if (scope is AMBIGUOUS_STAFF_ORIGIN_SCOPE
                    or scope is not NO_STAFF_ORIGIN_SCOPE and scope != user.staff_makerspace_id):
                raise AuthenticationFailed("Invalid account context.")


def validate_account_token(user, token):
    _active(user)
    if token.get("kind") != user.account_kind:
        raise AuthenticationFailed("Invalid account context.")
    if user.account_kind == "staff":
        if str(token.get("makerspace") or "") != str(user.staff_makerspace_id):
            raise AuthenticationFailed("Invalid account context.")
    elif token.get("makerspace") is not None:
        raise AuthenticationFailed("Invalid account context.")
    assert_surface(user, token.get("surface"))


def _platform_route(name):
    return name in PLATFORM_ROUTES or bool(name and name.startswith("admin-staff-account"))


def _delegated(user, targets, name):
    from apps.accounts.rbac_organizations import _org_actions_for, has_any_org_authority
    from apps.makerspaces.resource_grant_sources import has_authority
    # Organization governance routes have no tenant of their own. Their views check
    # the particular organization; a grant in one organization cannot authorize another.
    if name and (name.startswith("admin-organization") or name == "organization-analytics"):
        from apps.organizations.governance import has_any_governance
        if has_any_governance(user):
            return True
    if targets:
        return all(_org_actions_for(user, target) or has_authority(user, makerspace_ids=[target])
                   for target in targets)
    return has_any_org_authority(user) or has_authority(user)


def enforce_request(user, token, request):
    validate_account_token(user, token)
    assert_surface(user, token.get("surface"), request)
    from apps.accounts.authentication import _member_surface_path_allowed
    from apps.makerspaces.origin_scope_routes import request_route_targets
    match = getattr(request, "resolver_match", None)
    name = getattr(match, "url_name", None)
    classification = route_class(name)
    _name, targets, invalid, _recognized = request_route_targets(request)
    kind = user.account_kind
    if kind == "staff":
        if invalid or targets - {user.staff_makerspace_id}:
            raise PermissionDenied("Account context does not match this makerspace.")
        if classification is None or request.path.startswith("/api/v1/admin/platform/"):
            raise PermissionDenied("Staff account context is required.")
        if classification != SHARED_ACCOUNT_UTILITY and request.path.startswith("/api/v1/auth/"):
            raise PermissionDenied("Use a member account for this action.")
        request.selected_makerspace_id = user.staff_makerspace_id
        return
    if kind == "platform":
        if classification != SHARED_ACCOUNT_UTILITY and not _platform_route(name):
            raise PermissionDenied("Platform account context is required.")
        return
    if classification == SHARED_ACCOUNT_UTILITY:
        return
    if classification is None and request.path.startswith("/api/v1/auth/"):
        raise PermissionDenied("Unknown account route.")
    if _member_surface_path_allowed(request.path):
        return
    if classification != DELEGABLE or invalid or not _delegated(user, targets, name):
        raise PermissionDenied("A delegated authority source is required.")
