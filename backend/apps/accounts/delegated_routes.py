"""Account surface classifications; authorization remains in each route's service."""

from types import MappingProxyType

from .delegated_route_catalog import (
    DELEGABLE_ROUTES, MEMBER_ROUTES, MEMBERSHIP_ROUTES, PLATFORM_ONLY_ROUTES,
    SHARED_ROUTES, SIGNED_PROTOCOL_ROUTES, TENANT_STAFF_ROUTES,
)

MEMBERSHIP_ONLY = "membership-only"
DELEGABLE = "delegable"
SHARED_ACCOUNT_UTILITY = "shared-account-utility"
MEMBER_ONLY = "member-only"
PLATFORM_ONLY = "platform-only"
SIGNED_PROTOCOL = "signed-protocol"

ROUTE_CLASSES = MappingProxyType({
    **dict.fromkeys((
        "admin-staff-accounts", "admin-staff-account-policy", "admin-staff-account-change",
        "admin-staff-account-deactivate", "admin-staff-account-reactivate",
        "admin-staff-account-set-password", "admin-staff-account-resend-invite",
    ), MEMBERSHIP_ONLY),
    **dict.fromkeys(MEMBERSHIP_ROUTES, MEMBERSHIP_ONLY),
    **dict.fromkeys(DELEGABLE_ROUTES, DELEGABLE),
    **dict.fromkeys(SHARED_ROUTES, SHARED_ACCOUNT_UTILITY),
    **dict.fromkeys(TENANT_STAFF_ROUTES, MEMBERSHIP_ONLY),
    **dict.fromkeys(MEMBER_ROUTES, MEMBER_ONLY),
    **dict.fromkeys(PLATFORM_ONLY_ROUTES, PLATFORM_ONLY),
    **dict.fromkeys(SIGNED_PROTOCOL_ROUTES, SIGNED_PROTOCOL),
})


def route_class(url_name) -> str | None:
    """Look up a bare Django URL name. Unknown names never inherit a class."""
    return ROUTE_CLASSES.get(url_name)
