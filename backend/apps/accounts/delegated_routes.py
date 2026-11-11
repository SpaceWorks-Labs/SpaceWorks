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
       if "library" in name or "tenant-admin" in name},
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
    # Contextual equipment routes share the existing tenant staff boundary;
    # their views separately scope inventory actions and event/booking grants.
    "contextual-request-staff": DELEGABLE,
    "equipment-kit-list": DELEGABLE,
    "equipment-kit-detail": DELEGABLE,
    "equipment-kit-version": DELEGABLE,
    "equipment-kit-publication": DELEGABLE,
    "equipment-kit-archive": DELEGABLE,
    "admin-consumable-equipment-sources": DELEGABLE,
    "event-equipment-request-products": DELEGABLE,
    "event-equipment-kits": DELEGABLE,
    # Event-day desk: event VIEW and issue_request are each re-checked in the view.
    "event-equipment-desk": DELEGABLE,
    # 221b: window availability and bulk per-person planning re-check event + inventory authority.
    "event-equipment-availability": DELEGABLE,
    "event-equipment-plan": DELEGABLE,
    "booking-equipment-request-products": DELEGABLE,
    "booking-equipment-kits": DELEGABLE,
    "admin-request-event-context": DELEGABLE,
    "admin-direct-loan-event-context": DELEGABLE,
    "admin-request-booking-context": DELEGABLE,
    "admin-direct-loan-booking-context": DELEGABLE,
    # Decision 216 item 13: event/booking grants reach the subject; each section
    # (presence, machine sessions) re-checks its own tenant action and scope.
    "admin-related-facts-event": DELEGABLE,
    "admin-related-facts-booking": DELEGABLE,
    # Decision 216: tenant-wide events + bookings roles, session only; the staff price
    # preview shares the staff booking-create boundary.
    "admin-event-booking-link": MEMBERSHIP_ONLY,
    "admin-event-booking-replacement": MEMBERSHIP_ONLY,
    # P2-1 workshop machine links: the same tenant-wide roles plus machine authority.
    "admin-event-workshop-machines": MEMBERSHIP_ONLY,
    "admin-event-workshop-machine-replacement": MEMBERSHIP_ONLY,
    "admin-event-workshop-machine-link": MEMBERSHIP_ONLY,
    "admin-space-booking-quote": MEMBERSHIP_ONLY,
    # Decision 216 item 4: the read-only admission readiness beside the same form.
    "admin-space-booking-readiness": MEMBERSHIP_ONLY,
    "admin-booking-readiness": MEMBERSHIP_ONLY,
    # The free/busy picker beside the same form (event hall booking).
    "admin-space-booking-availability": MEMBERSHIP_ONLY,
    # Browser push proves installation ownership through the personal account surface.
    "browser-firebase-global-may-resume": MEMBER_ONLY,
    "browser-firebase-config": MEMBER_ONLY,
    "browser-firebase-may-resume": MEMBER_ONLY,
    "browser-firebase-challenge": MEMBER_ONLY,
    "browser-firebase-confirm": MEMBER_ONLY,
    # Anonymous first-party session-presence metadata, never identity or a token.
    "auth-browser-state": SHARED_ACCOUNT_UTILITY,
})


def route_class(url_name) -> str | None:
    """Look up a bare Django URL name. Unknown names never inherit a class."""
    return ROUTE_CLASSES.get(url_name)
