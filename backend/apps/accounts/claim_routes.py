"""Single authority for claim-reachable paths and their per-method policies."""

from apps.accounts.claim_route_types import (
    Allowed,
    AnonymousRead,
    BODY_OBJECT,
    ControlRoute,
    ID,
    LocallyFiltered,
    PUBLIC_TOKEN,
    ReadOnly,
    Refused,
    RowOwnership,
    SLUG,
)
from apps.accounts.claim_routes_auth import AUTH_CLAIM_ROUTES
from apps.accounts.claim_routes_member import MEMBER_CLAIM_ROUTES
from apps.accounts.claim_routes_public import PUBLIC_CLAIM_ROUTES
from apps.accounts.delegated_route_catalog import ACCOUNT_MERGE_ROUTES, STAFF_ROLE_ROUTES


CLAIM_REACHABLE_PREFIXES = (
    "/api/v1/auth/",
    "/api/v1/member/",
    "/api/v1/memberships/",
    "/api/v1/public/",
)


from .claim_routes_profiles import PROFILE_CLAIM_ROUTES
from .claim_routes_public_pages import PUBLIC_PAGE_CLAIM_ROUTES
from .claim_routes_membership_l4 import L4_CLAIM_ROUTES
from .claim_routes_r2 import R2_CLAIM_ROUTES
from .claim_routes_l3 import L3_CLAIM_ROUTES
from .claim_routes_l6 import L6_CLAIM_ROUTES
from .claim_routes_l18 import L18_CLAIM_ROUTES

from .claim_routes_p2_presence import ROUTES as PRESENCE_ROUTES
from .claim_routes_programme import CLAIM_ROUTES as PROGRAMME_CLAIM_ROUTES
from .claim_routes_reimbursements import CLAIM_ROUTES as REIMBURSEMENT_CLAIM_ROUTES

CLAIM_ROUTES = {
    **PUBLIC_PAGE_CLAIM_ROUTES,
    **PROGRAMME_CLAIM_ROUTES,
    **REIMBURSEMENT_CLAIM_ROUTES,
    **PRESENCE_ROUTES,
    **PROFILE_CLAIM_ROUTES,
    **PUBLIC_CLAIM_ROUTES,
    **MEMBER_CLAIM_ROUTES,
    **L4_CLAIM_ROUTES,
    **R2_CLAIM_ROUTES,
    **L3_CLAIM_ROUTES,
    **L6_CLAIM_ROUTES,
    **L18_CLAIM_ROUTES,
    **AUTH_CLAIM_ROUTES,
}


def policy_for(view_name, method):
    """Fail closed at runtime even before the build guard reports route drift."""
    if view_name == "notification-media":
        return Refused("Media delivery requires its own single-use capability")
    if view_name in STAFF_ACCOUNT_REFUSALS:
        return Refused("Claim sessions cannot manage staff accounts")
    return CLAIM_ROUTES.get(
        (view_name, method.upper()),
        Refused("unclassified claim route"),
    )


# Outside CLAIM_REACHABLE_PREFIXES: keep these explicit denials separate from the
# exact reachable-route matrix so it does not acquire stale entries.
STAFF_ACCOUNT_REFUSALS = frozenset({
    "admin-staff-accounts", "admin-staff-account-policy", "admin-staff-account-change",
    "admin-staff-account-deactivate", "admin-staff-account-reactivate",
    "admin-staff-account-set-password", "admin-staff-account-resend-invite",
    # Release 2: staff roles and account merges are never reachable from a claim session.
    *STAFF_ROLE_ROUTES, *ACCOUNT_MERGE_ROUTES,
})


__all__ = (
    "Allowed",
    "AnonymousRead",
    "BODY_OBJECT",
    "CLAIM_REACHABLE_PREFIXES",
    "CLAIM_ROUTES",
    "ControlRoute",
    "ID",
    "LocallyFiltered",
    "PUBLIC_TOKEN",
    "ReadOnly",
    "Refused",
    "RowOwnership",
    "SLUG",
    "policy_for",
)
