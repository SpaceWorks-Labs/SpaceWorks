"""Origin-scope tables for staff routes a phone reaches with a native `X-Makerspace-Id` (decision 353, MOB-STAFF).

A native staff grant is fixed to one makerspace, so every staff route it calls must name that makerspace
(path, object, body, query) or be explicitly space-neutral. A header that disagrees with the resolved
target is refused (403) by `validate_native_makerspace_scope`.
"""

from apps.accounts.programme_route_catalog import BY_NAME as _PROGRAMME, NATIVE_WEB_ONLY as _PROGRAMME_WEB_ONLY

# The event programme's staff routes (`events-programme-admin-*` plus the series guest list) name only their event
# or series by `pk`; the target is its hosting makerspace, for the web origin scope, the tenant source gate, RLS
# and the native header alike. Tenant-kind routes carry `makerspace_id` or a query and are tabled elsewhere.
PROGRAMME_MODEL_LOOKUPS = {
    name: ({"event": "events.Event", "series": "events.EventSeries"}[kind], "makerspace_id")
    for name, (_methods, kind) in _PROGRAMME.items()
    if (name.startswith("events-programme-admin-") or name == "events-programme-series-guests")
    and kind in ("event", "series") and name not in _PROGRAMME_WEB_ONLY
}

MODEL_LOOKUPS = {
    **PROGRAMME_MODEL_LOOKUPS,
    "admin-event-image": ("events.Event", "makerspace_id"),
    "admin-space-organization-booking": ("bookings.BookableSpace", "makerspace_id"),
    "admin-space-organization-booking-choices": ("bookings.BookableSpace", "makerspace_id"),
}
# Read ONLY for a native header (`origin_scope_native_staff`), never by the web resolver: the owner FK is nullable.
# A global API client (no makerspace) is the superadmin's, and must keep resolving to "no target" for the web
# superadmin; for a native staff grant it resolves to nothing, so the header is refused.
NATIVE_ONLY_LOOKUPS = {
    "admin-api-client": ("apiclients.ApiClient", "makerspace_id"),
    "admin-api-client-rotate-secret": ("apiclients.ApiClient", "makerspace_id"),
}
# The URL id is the OAuth application id, not the registration row's own pk.
TARGET_SET_LOOKUPS = {
    "admin-oauth-app": ("apiclients.OAuthAppRegistration", "application_id", "makerspace_id"),
}
# The body names the space (and the view requires it to equal the checked space).
BODY_SCOPED_ROUTES = {"telegram-test-alert"}
# Listings narrowed by `?makerspace=`; a native request must name the selected space there.
QUERY_SCOPED_ROUTES = {"events-programme-admin-space-insights"}
# Space-neutral by design: the view lists or decides only what the caller's own (single-tenant, native)
# authority already reaches, so there is no target to compare. The selected space still pins the grant.
#  - admin-makerspaces / admin-event-host-options: switcher and host pickers, scoped by RBAC + the selection.
#  - admin-bulk-*: per-row authority inside one all-or-nothing transaction, as the single-item routes.
NATIVE_HEADER_GLOBAL_ROUTES = {
    "admin-makerspaces", "admin-event-host-options",
    "admin-bulk-requests", "admin-bulk-bookings", "admin-bulk-event-registrations",
}

# Staff-classed routes the web SPA calls that a native staff grant deliberately cannot reach. They stay
# unrecognized, so the header is refused ("Makerspace target could not be resolved").
_SUPERADMIN = "superadmin-only; a superadmin never holds a phone token (decision 356)"
_ORG = "organization-derived authority is web-only: native sessions carry local membership authority only"
NATIVE_STAFF_WEB_ONLY = {
    "admin-backup-download-url": _SUPERADMIN,
    "admin-machine-service-report": _SUPERADMIN,
    "admin-space-pack-profiles": _SUPERADMIN,
    "events-programme-admin-my-application-reviews": "event-role desk, web-only by decision 173",
    **{name: _SUPERADMIN for name in (
        "admin-backup-destinations", "admin-platform-backup-settings", "admin-deployment-backups",
        "admin-backup-archive-rehydrate", "admin-platform-dashboard", "admin-platform-email-settings",
        "admin-platform-payment-settings", "admin-platform-problems", "admin-restore-operations",
        "admin-restore-operation", "admin-restore-decision", "admin-platform-social-auth-settings",
    )},
    "user-restrict": _SUPERADMIN,
    "user-restore-access": _SUPERADMIN,
    "report-catalog-aggregate": _SUPERADMIN,
    "booking-staff-invite-redeem": "native member sessions never redeem booking staff invites (surface_policy)",
    "admin-organized-event-attendance": _ORG,
    "admin-organized-event-list": _ORG,
    "events-programme-admin-organization-insights": _ORG,
    **{name: _ORG for name in (
        "admin-organization-list", "admin-organization-detail", "admin-organization-invitation-revoke",
        "admin-organization-email-sender", "admin-organization-hosting-invitations",
        "admin-organization-hours-bank", "admin-organization-invitations", "admin-organization-links",
        "admin-organization-member-rollup", "admin-organization-memberships",
        "admin-organization-membership-detail", "admin-organization-resubmit", "admin-organization-review",
        "admin-organization-id-programmes",
    )},
}
