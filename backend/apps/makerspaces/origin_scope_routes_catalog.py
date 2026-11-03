"""Origin-scope route tables: which URL names resolve their tenant, and how.

Split out of ``origin_scope_routes`` (file ceiling); that module re-exports every table.
"""

from apps.makerspaces.origin_scope_model_lookups import (
    BASE_MODEL_LOOKUPS,
    TARGET_SET_LOOKUPS,
)

PUBLIC_SLUG_ROUTES = {"public-presence-now", "presence-start", "presence-current", "presence-end", "presence-renew", "presence-projects", "presence-preferences", "public-booking-resource", "public-booking-website", "public-booking-website-image", "member-booking-pass", "member-booking-confirmation", "member-booking-confirmation-png", "member-booking-calendar", "member-booking-rotate-checkin", "public-event-organization-eligibility"}

REPLAY_TOKEN_ROUTES = {"kiosk-replay-prepare", "kiosk-replay-execute"}
# Owner controls resolve their tenant from the job's tracking token (C16).
SERVICE_TOKEN_ROUTES = {"member-machine-service-owner"}

# Scanner routes carry their tenant inside the scanned QR payload, not the path. The
# target is the QR's makerspace, so a native staff session cannot scan another space's
# QR under its selected header. An unknown payload adds no target; the view 404s.
QR_PAYLOAD_ROUTES = {"qr-resolve", "qr-scan"}

# Only these creation routes take their authoritative tenant from the body.
BODY_SCOPED_ROUTES = {"qr-boxes", "qr-containers", "qr-tools"}

MAKERSPACE_KWARG_ROUTES = {
    **{name: "makerspace_id" for name in (
        "admin-staff-accounts", "admin-staff-account-policy", "admin-staff-account-change",
        "admin-staff-account-deactivate", "admin-staff-account-reactivate",
        "admin-staff-account-set-password", "admin-staff-account-resend-invite",
    )},
    "whatsapp-meta-webhook": "makerspace_id",
    "email-provider-webhook": "makerspace_id",
    "website-origins": "makerspace_id",
    'admin-booking-machine-types': 'makerspace_id',
    'admin-makerspace-setup-state': 'makerspace_id',
    'admin-maintenance-overdue': 'makerspace_id',
    'admin-makerspace-profile': 'makerspace_id',
    'admin-makerspace-domain-settings': 'makerspace_id',
    'admin-settings-authority-grants': 'makerspace_id',
    'admin-settings-authority-locks': 'makerspace_id',
    'admin-settings-authority-effective': 'makerspace_id',
    'admin-makerspace-usage': 'makerspace_id',
    'admin-kiosk-replay-list': 'makerspace_id',
    'admin-maintenance-schedule-list-create': 'makerspace_id',
    'admin-maintenance-log-list-create': 'makerspace_id',
    'admin-bookable-space-list-create': 'makerspace_id',
    'admin-event-list-create': 'makerspace_id',
    'admin-event-series-list-create': 'makerspace_id',
    'admin-event-series-collaboration-inbox': 'makerspace_id',
    'admin-role-list-create': 'makerspace_id',
    'admin-membership-machine-scope': 'makerspace_id',
    'admin-machine-types': 'makerspace_id',
    'admin-machine-type-detail': 'makerspace_id',
    'admin-makerspace-provision-subdomain': 'makerspace_id',
    'admin-makerspace-subdomain-request': 'makerspace_id',
    'admin-api-settings': 'makerspace_id',
    'admin-notification-recipients': 'makerspace_id',
    'admin-notification-rules': 'makerspace_id',
    'admin-machine-service-request-list-create': 'makerspace_id',
    'admin-audit-verifications': 'makerspace_id',
    'admin-audit-verification-detail': 'makerspace_id',
    'admin-kiosk-station-list-create': 'makerspace_id',
}
from .origin_scope_routes_7b import PRINTER_MAKERSPACE_ROUTES

MAKERSPACE_KWARG_ROUTES.update(PRINTER_MAKERSPACE_ROUTES)
MAKERSPACE_KWARG_ROUTES.update({name: "makerspace_id" for name in (
    "messaging-settings", "messaging-test", "whatsapp-template-list",
    "whatsapp-template-detail", "whatsapp-template-catalog",
)})
from .origin_scope_routes_wp4 import MAKERSPACE_ROUTES as WP4_ROUTES
MAKERSPACE_KWARG_ROUTES.update(WP4_ROUTES)
MAKERSPACE_KWARG_ROUTES.update({name: "makerspace_id" for name in (
    "contract-channels", "contract-channel", "contract-endpoints", "contract-endpoint-start",
    "contract-endpoint-verify", "contract-endpoint-revoke", "contract-preferences",
    "contract-deliveries", "contract-test",
)})

# These routes have no tenant-bearing path segment by design: each is a listing whose
# queryset is explicitly narrowed by the named makerspace query parameter.
QUERY_SCOPED_ROUTES = {
    "member-messaging",
    "member-messaging-consent",
    'admin-accessible-events',
    'admin-accessible-booking-spaces',
    'admin-search',                # ?makerspace_id= is mandatory
    'admin-api-key-requests',       # requester-owned API-key requests; ?makerspace=
    'admin-audit-logs',             # tenant audit-log listing; ?makerspace=
    'admin-membership-requests',    # tenant join-request queue; ?makerspace_id=
    'admin-memberships-roster',     # tenant membership roster; ?makerspace_id=
    'admin-needs-fix-shelf',        # tenant repair shelf; ?makerspace=
    'ledger-aggregate',             # superadmin aggregate listing; ?makerspace=
    'ledger-export-aggregate',      # matching aggregate export; ?makerspace=
}
NATIVE_HEADER_GLOBAL_ROUTES = {
    'auth-me',
    'device-grants',
    'device-grant-detail',
    'push-device-list-create',
    'push-device-detail',
    'auth-logout-all', 'auth-logout', 'device-logout', 'auth-reauth',
    'auth-reauth-phone-start', 'auth-reauth-phone-confirm', 'auth-reauth-social-factor',
}
REQUEST_ACTIONS = {
    'request-accept',
    'request-reject',
    'request-assign-box',
    'request-issue',
    'request-return-due',
    'request-return',
    'guest-admin-request-return',
    'request-timeline',
}
MACHINE_SERVICE_ACTIONS = {
    'admin-machine-service-request-detail',
    'admin-machine-service-request-accept',
    'admin-machine-service-request-reject',
    'admin-machine-service-request-start',
    'admin-machine-service-request-complete',
    'admin-machine-service-request-fail',
    'admin-machine-service-request-collect',
    'admin-machine-service-file-presign',
    'admin-machine-service-file-finalize',
    'admin-machine-service-request-cancel',
    'member-machine-service-cancel',
}
from .origin_scope_routes_w7_events import EVENT_MODEL_LOOKUPS
from .origin_scope_routes_p2_events import P2_EVENT_MODEL_LOOKUPS
MAKERSPACE_KWARG_ROUTES["admin-event-categories"] = "makerspace_id"

MODEL_LOOKUPS = {
    **EVENT_MODEL_LOOKUPS, **P2_EVENT_MODEL_LOOKUPS,
    **BASE_MODEL_LOOKUPS,
    **{name: ('hardware_requests.HardwareRequest', 'makerspace_id') for name in REQUEST_ACTIONS},
    **{name: ('machines.MachineServiceRequest', 'makerspace_id') for name in MACHINE_SERVICE_ACTIONS},
}
from .origin_scope_routes_p2_bookings import MODEL_LOOKUPS as P2_BOOKING_LOOKUPS
MODEL_LOOKUPS.update(P2_BOOKING_LOOKUPS)
from .origin_scope_routes_r2_l1 import MAKERSPACE_ROUTES as R2_L1_MAKERSPACE_ROUTES, MODEL_LOOKUPS as R2_L1_LOOKUPS
MAKERSPACE_KWARG_ROUTES.update(R2_L1_MAKERSPACE_ROUTES)
MODEL_LOOKUPS.update(R2_L1_LOOKUPS)
from .origin_scope_routes_r2_l10 import MODEL_LOOKUPS as R2_L10_LOOKUPS
MODEL_LOOKUPS.update(R2_L10_LOOKUPS)
from .origin_scope_routes_r2_l12 import MODEL_LOOKUPS as R2_L12_LOOKUPS
MODEL_LOOKUPS.update(R2_L12_LOOKUPS)
from .origin_scope_routes_r2_l23 import MODEL_LOOKUPS as R2_L23_LOOKUPS
MODEL_LOOKUPS.update(R2_L23_LOOKUPS)
