"""Scopes for credentials that act AS a person: personal access tokens and OAuth app connections (#196).

Such a credential never carries authority of its own. It authenticates the person, then
every live check that person's own session would face still runs (account state, the
surface and staff-role gates, MFA, RBAC in the view), and on top of that the scopes
narrow which route families it may touch and whether it may write:

    account:read / account:write   the person's own member surface (/api/v1/member/, /api/v1/me...)
    public:read / public:write     the public API, plus the narrower public:<area>:read|write
    staff:read / staff:write       staff console routes, in ONE named space only

Refused whatever the scopes say: sign-in, MFA, passkeys and every other /api/v1/auth/
route (so a token can never mint, see or revoke credentials), the Django control plane,
superadmin/platform routes, and the security and credential routes of the console.
"""
from django.utils.translation import gettext
from rest_framework.exceptions import PermissionDenied

ACCOUNT_READ, ACCOUNT_WRITE = "account:read", "account:write"
STAFF_READ, STAFF_WRITE = "staff:read", "staff:write"
PUBLIC_READ, PUBLIC_WRITE = "public:read", "public:write"
STAFF_SCOPES = frozenset({STAFF_READ, STAFF_WRITE})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

ACCOUNT_PREFIXES = ("/api/v1/member/", "/api/v1/me", "/api/v1/memberships", "/api/v1/notifications/")
STAFF_PREFIXES = ("/api/v1/admin/", "/api/v1/procurement/", "/api/v1/guest-admin/")
# Console routes that manage credentials or security: a session-only act, even for a
# Space Manager whose token holds staff:write.
CREDENTIAL_NAME_PARTS = ("api-client", "api-key", "api-settings", "access-token", "oauth", "security-settings",
                         "pii-access", "mfa", "passkey", "reauth", "staff-invitation", "staff-role",
                         "backup", "tenant-migration", "payment-settings", "integration-credential",
                         "account-session")


def person_scope_vocabulary():
    from .scope_registry import AREA_SCOPES
    return frozenset({ACCOUNT_READ, ACCOUNT_WRITE, PUBLIC_READ, PUBLIC_WRITE, STAFF_READ, STAFF_WRITE}) | AREA_SCOPES


def catalog():
    from .scope_grants import scope_catalog
    labels = {
        ACCOUNT_READ: ("My account (read)", "Read my own bookings, loans, cards, events and notices."),
        ACCOUNT_WRITE: ("My account (write)", "Act on my own records as I could in the app."),
        STAFF_READ: ("Staff console (read)", "Read what my staff roles in the chosen space allow."),
        STAFF_WRITE: ("Staff console (write)", "Do what my staff roles in the chosen space allow."),
    }
    rows = [{"value": value, "label": label, "description": description, "group": "Acting as me",
             "needs_space": value in STAFF_SCOPES} for value, (label, description) in labels.items()]
    rows += [{"value": row["value"], "label": row["label"], "description": row["description"],
              "group": row["group"], "needs_space": False}
             for row in scope_catalog(privileged=False) if row["grantable"]]
    return rows


def validate(scopes, *, makerspace, staff_space_ids):
    """Return the scopes after the grant policy, or raise ValueError."""
    values = list(scopes or [])
    if not values or len(values) != len(set(values)):
        raise ValueError("Choose at least one scope, each once.")
    unknown = sorted(set(values) - person_scope_vocabulary())
    if unknown:
        raise ValueError(f"Unknown scope(s): {', '.join(unknown)}.")
    wants_staff = bool(set(values) & STAFF_SCOPES)
    if wants_staff and makerspace is None:
        raise ValueError("Staff scopes need the space they apply to.")
    if wants_staff and makerspace.pk not in staff_space_ids:
        raise ValueError("You hold no staff role in that space.")
    if not wants_staff and makerspace is not None:
        raise ValueError("A space is chosen only with staff scopes.")
    return values


def _credential_route(request, name):
    from apps.accounts.surface_policy import PLATFORM_ROUTES
    lowered = (name or "").lower()
    return (request.path.startswith(("/api/v1/auth/", "/control/", "/api/v1/admin/platform/"))
            or name in PLATFORM_ROUTES or any(part in lowered for part in CREDENTIAL_NAME_PARTS))


def admit(request, scopes, makerspace_id):
    """Raise PermissionDenied unless these scopes reach this route with this method."""
    from apps.apiclients import scope_registry
    scopes = frozenset(scopes or ())
    method = request.method.upper()
    access = "read" if method in SAFE_METHODS else "write"
    name = getattr(getattr(request, "resolver_match", None), "url_name", None)
    if _credential_route(request, name):
        raise PermissionDenied(gettext("Tokens cannot reach sign-in, security or credential routes."))
    path = request.path
    if path.startswith(tuple("/" + prefix for prefix in scope_registry._protected_prefixes())):
        entry = scope_registry.lookup(scope_registry.resolve_view_name(request), method)
        broad = PUBLIC_READ if access == "read" else PUBLIC_WRITE
        area = f"public:{entry.area}:{entry.access}" if entry is not None and entry.area else None
        if broad in scopes or (area is not None and area in scopes):
            return
        raise PermissionDenied(gettext("This token's scopes do not include this public route."))
    if path.startswith(ACCOUNT_PREFIXES):
        if (ACCOUNT_READ if access == "read" else ACCOUNT_WRITE) in scopes:
            return
        raise PermissionDenied(gettext("This token's scopes do not include your account routes."))
    if path.startswith(STAFF_PREFIXES):
        if (STAFF_READ if access == "read" else STAFF_WRITE) not in scopes or makerspace_id is None:
            raise PermissionDenied(gettext("This token's scopes do not include staff routes."))
        from apps.makerspaces.origin_scope_routes import request_route_targets
        _name, targets, invalid, _recognized = request_route_targets(request)
        if invalid or set(targets) != {makerspace_id}:
            raise PermissionDenied(gettext("This token reaches staff routes of its own space only."))
        return
    raise PermissionDenied(gettext("Tokens cannot reach this route."))
