"""Account surface classifications; authorization remains in each route's service."""

from types import MappingProxyType

from .delegated_route_catalog import DELEGABLE_ROUTES, MEMBERSHIP_ROUTES, SHARED_ROUTES
from .programme_route_catalog import ROUTES as PROGRAMME_ROUTES
from .reimbursement_route_catalog import ROUTES as REIMBURSEMENT_ROUTES

MEMBERSHIP_ONLY = "membership-only"
DELEGABLE = "delegable"
SHARED_ACCOUNT_UTILITY = "shared-account-utility"

ROUTE_CLASSES = MappingProxyType({
    **{name: (MEMBERSHIP_ONLY if target == "tenant" else DELEGABLE)
       for name, methods, target in PROGRAMME_ROUTES if name.startswith("events-programme-admin-")},
    **{name: MEMBERSHIP_ONLY for name, methods, target in PROGRAMME_ROUTES
       if "library" in name or "tenant-admin" in name or name == "admin-platform-insights"},
    "events-programme-series-guests": DELEGABLE,
    **{name: (DELEGABLE if surface == "delegable" else MEMBERSHIP_ONLY)
       for name, methods, target, surface in REIMBURSEMENT_ROUTES if surface != "member"},
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
