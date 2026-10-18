"""Account surface classifications; authorization remains in each route's service."""

from types import MappingProxyType

from .delegated_route_catalog import DELEGABLE_ROUTES, MEMBERSHIP_ROUTES, SHARED_ROUTES
from .claim_routes_public_pages import MAKERSPACE_PAGE_EDITORS, ORGANIZATION_PAGE_EDITORS

MEMBERSHIP_ONLY = "membership-only"
DELEGABLE = "delegable"
SHARED_ACCOUNT_UTILITY = "shared-account-utility"

ROUTE_CLASSES = MappingProxyType({
    **dict.fromkeys(MAKERSPACE_PAGE_EDITORS, MEMBERSHIP_ONLY),
    **dict.fromkeys(ORGANIZATION_PAGE_EDITORS, DELEGABLE),
    **dict.fromkeys((
        "admin-staff-accounts", "admin-staff-account-policy", "admin-staff-account-change",
        "admin-staff-account-deactivate", "admin-staff-account-reactivate",
        "admin-staff-account-set-password", "admin-staff-account-resend-invite",
    ), MEMBERSHIP_ONLY),
    **dict.fromkeys(MEMBERSHIP_ROUTES, MEMBERSHIP_ONLY),
    **dict.fromkeys(DELEGABLE_ROUTES, DELEGABLE),
    **dict.fromkeys(SHARED_ROUTES, SHARED_ACCOUNT_UTILITY),
})


def route_class(url_name) -> str | None:
    """Look up a bare Django URL name. Unknown names never inherit a class."""
    return ROUTE_CLASSES.get(url_name)
