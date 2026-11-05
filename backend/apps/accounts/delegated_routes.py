"""Account surface classifications; authorization remains in each route's service."""

from types import MappingProxyType

from .delegated_route_catalog import (
    ACCOUNT_MERGE_ROUTES, DELEGABLE_ROUTES, MEMBER_ROUTES, MEMBERSHIP_ROUTES, PLATFORM_ONLY_ROUTES,
    SHARED_ROUTES, SIGNED_PROTOCOL_ROUTES, STAFF_ROLE_ROUTES, TENANT_STAFF_ROUTES,
)
from .claim_routes_public_pages import MAKERSPACE_PAGE_EDITORS, ORGANIZATION_PAGE_EDITORS
from .passkey_route_catalog import PASSKEY_CEREMONY_ROUTES, PASSKEY_ROUTES
from .login_risk_route_catalog import LOGIN_RISK_ANONYMOUS_ROUTES, LOGIN_RISK_ROUTES
from .programme_route_catalog import ROUTES as PROGRAMME_ROUTES
from .reimbursement_route_catalog import ROUTES as REIMBURSEMENT_ROUTES
from .security_route_catalog import ROUTES as SECURITY_ROUTES

PERSON_CREDENTIAL_ROUTES = frozenset({
    "auth-access-tokens", "auth-access-token-revoke", "auth-access-token-scopes", "auth-oauth-consent",
    "auth-connected-apps", "auth-connected-app-revoke",
})
OAUTH_APP_ROUTES = frozenset({"admin-oauth-apps", "admin-oauth-app"})
# The OAuth protocol endpoints authenticate the CLIENT (secret or PKCE), never a person session.
OAUTH_PROTOCOL_ROUTES = frozenset({"authorize", "token", "revoke-token", "introspect",
                                   "oidc-connect-discovery-info", "jwks-info", "user-info"})

MEMBERSHIP_ONLY = "membership-only"
DELEGABLE = "delegable"
SHARED_ACCOUNT_UTILITY = "shared-account-utility"
MEMBER_ONLY = "member-only"
PLATFORM_ONLY = "platform-only"
SIGNED_PROTOCOL = "signed-protocol"

ROUTE_CLASSES = MappingProxyType({
    **dict.fromkeys(MAKERSPACE_PAGE_EDITORS, MEMBERSHIP_ONLY),
    **dict.fromkeys(ORGANIZATION_PAGE_EDITORS, DELEGABLE),
    **{name: (MEMBERSHIP_ONLY if target == "tenant" else DELEGABLE)
       for name, methods, target in PROGRAMME_ROUTES if name.startswith("events-programme-admin-")},
    **{name: MEMBERSHIP_ONLY for name, methods, target in PROGRAMME_ROUTES
       if "library" in name or "tenant-admin" in name or name == "admin-platform-insights"},
    "events-programme-series-guests": DELEGABLE,
    **{name: (DELEGABLE if surface == "delegable" else MEMBERSHIP_ONLY)
       for name, methods, target, surface in REIMBURSEMENT_ROUTES if surface != "member"},
    # Release 2 (one account per person): U-B's staff-roles API and S-A's MFA reset
    # replaced the staff-account routes; U-C's account-merge routes are a person's own.
    **dict.fromkeys(STAFF_ROLE_ROUTES, MEMBERSHIP_ONLY),
    **dict.fromkeys(ACCOUNT_MERGE_ROUTES, MEMBER_ONLY),
    **dict.fromkeys(MEMBERSHIP_ROUTES, MEMBERSHIP_ONLY),
    **dict.fromkeys(SECURITY_ROUTES, MEMBERSHIP_ONLY),
    **dict.fromkeys(PASSKEY_ROUTES, MEMBER_ONLY),
    **dict.fromkeys(PASSKEY_CEREMONY_ROUTES, SHARED_ACCOUNT_UTILITY),
    **dict.fromkeys(LOGIN_RISK_ROUTES, MEMBER_ONLY),
    **dict.fromkeys(LOGIN_RISK_ANONYMOUS_ROUTES, SHARED_ACCOUNT_UTILITY),
    **dict.fromkeys(DELEGABLE_ROUTES, DELEGABLE),
    **dict.fromkeys(SHARED_ROUTES, SHARED_ACCOUNT_UTILITY),
    **dict.fromkeys(TENANT_STAFF_ROUTES, MEMBERSHIP_ONLY),
    **dict.fromkeys(MEMBER_ROUTES, MEMBER_ONLY),
    **dict.fromkeys(PLATFORM_ONLY_ROUTES, PLATFORM_ONLY),
    **dict.fromkeys(SIGNED_PROTOCOL_ROUTES, SIGNED_PROTOCOL),
    # #196: a person's own tokens and app connections; registering apps is tenant staff.
    **dict.fromkeys(PERSON_CREDENTIAL_ROUTES, MEMBER_ONLY),
    **dict.fromkeys(OAUTH_APP_ROUTES, MEMBERSHIP_ONLY),
    **dict.fromkeys(OAUTH_PROTOCOL_ROUTES, SIGNED_PROTOCOL),
})


def route_class(url_name) -> str | None:
    """Look up a bare Django URL name. Unknown names never inherit a class."""
    return ROUTE_CLASSES.get(url_name)
