"""The platform superadmin's way into a makerspace's staff routes (owner decision #115).

The account split kept tenant operations on staff accounts. #115 reverses that for the
superadmin alone: in the staff console they choose a space and see and use exactly what
that space's Space Manager does -- every report, analytics page, export and setting.

This module only opens the surface. Each route still applies its own RBAC (global for
the superadmin, `rbac.can`), module gates, servability, recent re-authentication and
audit, so nothing here grants an action by itself. Routes outside the staff surface stay
closed: unknown names, member-only and signed-protocol routes, and the `/api/v1/auth/`
identity routes (sign-in, sign-up, phone and social linking belong to member accounts).
"""

from apps.accounts.delegated_routes import DELEGABLE, MEMBERSHIP_ONLY
from apps.accounts.staff_identity import is_platform

TENANT_CLASSES = frozenset({MEMBERSHIP_ONLY, DELEGABLE})
_AUTH_PREFIX = "/api/v1/auth/"


def is_platform_superadmin(user):
    return bool(
        user is not None
        and is_platform(user)
        and user.is_superuser
        and user.role == "superadmin"
    )


def admits(user, request, classification, targets, invalid, *, native=False):
    """Whether a platform superadmin may enter this tenant staff route."""
    if native or invalid or classification not in TENANT_CLASSES:
        return False
    if request.path.startswith(_AUTH_PREFIX) or not is_platform_superadmin(user):
        return False
    from apps.accounts.platform_tenant_pii import refuse_masked_write, remember_spaces
    refuse_masked_write(request)
    remember_spaces(request, targets, user)
    return True
