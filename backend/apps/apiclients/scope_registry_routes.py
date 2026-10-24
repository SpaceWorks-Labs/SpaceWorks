from dataclasses import dataclass
from types import MappingProxyType


PUBLIC_READ = "public:read"
PUBLIC_WRITE = "public:write"
PUBLIC_ALL = "public:*"

TARGET_GLOBAL = "global"
TARGET_TENANT_SLUG = "tenant_slug"
TARGET_TENANT_TOKEN = "tenant_token"
TARGET_CLIENT_SUBJECT = "client_subject"
TARGET_PUBLIC_HANDLE = "public_handle"
TARGET_MODES = frozenset({TARGET_GLOBAL, TARGET_TENANT_SLUG, TARGET_TENANT_TOKEN,
                          TARGET_CLIENT_SUBJECT, TARGET_PUBLIC_HANDLE})

PUBLIC_READ_SCOPES = frozenset({PUBLIC_READ, PUBLIC_ALL})
PUBLIC_WRITE_SCOPES = frozenset({PUBLIC_WRITE, PUBLIC_ALL})


@dataclass(frozen=True, slots=True)
class ScopeRegistryEntry:
    scopes: frozenset[str]
    target_mode: str
    tenant_apps_admitted: bool = False
    legacy_v1: bool = False
    server_only: bool = False
    tenant_bound: bool = False
    required_scopes: frozenset[str] = frozenset()


_READ = ("GET", "HEAD")
_WRITE = ("POST",)

# Each definition is (fully-qualified resolver view_name, concrete methods, scopes,
# target mode, tenant-app admission, legacy-v1 admission). Legacy admission is explicit
# so adding a route cannot silently widen the frozen cutover capability.
_ROUTE_DEFINITIONS = (
    ("public-page-handle", _READ, PUBLIC_READ_SCOPES, TARGET_PUBLIC_HANDLE, True, False),
    ("public-event-code", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_TOKEN, False, False),
    *tuple((name, _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, False) for name in (
        "public-makerspace-page", "public-makerspace-page-asset",
    )),
    *tuple((name, _READ, PUBLIC_READ_SCOPES, TARGET_GLOBAL, True, False) for name in (
        "public-organization-page", "public-organization-page-asset", "public-organization-makerspaces",
    )),
    # /api/v1/discover/ is outside HMAC_PROTECTED_PATH_PREFIXES, so "website-discover"
    # must not be registered: an entry there is stale by construction.
    *tuple((name, _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_TOKEN, False, False) for name in (
        "public-profile", "public-profile-activity", "public-profile-events", "public-profile-projects", "public-profile-github",
    )),
    *tuple((name, _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, False) for name in (
        "public-booking-resource", "public-booking-website", "public-booking-website-image",
    )),
    ("member-booking-pass", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, False),
    ("member-booking-confirmation", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, False),
    ("member-booking-confirmation-png", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, False),
    ("member-booking-calendar", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, False),
    ("member-booking-rotate-checkin", _WRITE, PUBLIC_WRITE_SCOPES, TARGET_TENANT_SLUG, False, False),
    *tuple((name, _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, False) for name in ("public-event-website", "public-event-website-section", "public-event-website-session", "public-event-website-image", "public-event-website-schedule", "public-event-website-speaker")),
    ("member-booking-reschedule", _WRITE, PUBLIC_WRITE_SCOPES, TARGET_TENANT_SLUG, False, False),
    ("member-booking-feed-settings", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, False),
    ("member-booking-feed-settings", ("POST", "DELETE"), PUBLIC_WRITE_SCOPES, TARGET_TENANT_SLUG, False, False),
    ("public-booking-feed", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, False),
    ('member-booking-list', _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, False),
    ('member-booking-cancel', _WRITE, PUBLIC_WRITE_SCOPES, TARGET_TENANT_SLUG, False, False),
    ('member-booking-checkout', _WRITE, PUBLIC_WRITE_SCOPES, TARGET_TENANT_SLUG, False, False),
    ('public-event-venue', _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, False),
    ("public-makerspaces", _READ, PUBLIC_READ_SCOPES, TARGET_GLOBAL, True, True),
    ("v1:public-makerspaces", _READ, PUBLIC_READ_SCOPES, TARGET_GLOBAL, True, True),
    ("public-inventory", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, True),
    ("public-makerspace-stats", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, True),
    ("public-inventory-categories", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, True),
    ("public-inventory-detail", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, True),
    ("v1:public-inventory", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, True),
    ("v1:public-makerspace-stats", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, True),
    ("v1:public-inventory-categories", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, True),
    ("v1:public-inventory-detail", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, True),
    ("public-machines", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, True),
    (
        "public-machine-service-request-submit", _WRITE, PUBLIC_WRITE_SCOPES,
        TARGET_TENANT_SLUG, False, True,
    ),
    ("public-printer-service-queues", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, True),
    ("public-printer-service-pools", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, True),
    ("public-printer-service-upload", _WRITE, PUBLIC_WRITE_SCOPES, TARGET_TENANT_SLUG, False, True),
    (
        "public-printer-service-request", _WRITE, PUBLIC_WRITE_SCOPES,
        TARGET_TENANT_SLUG, False, True,
    ),
    ("public-event-organization-eligibility", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, False),
    ("public-event-detail", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, False),
    ("public-event-list", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, True),
    ("public-organization-detail", _READ, PUBLIC_READ_SCOPES, TARGET_GLOBAL, True, True),
    ("public-organization-events", _READ, PUBLIC_READ_SCOPES, TARGET_GLOBAL, True, True),
    ("public-event-calendar", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, True),
    ("public-event-calendar-feed", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, True),
    ("public-event-register", _WRITE, PUBLIC_WRITE_SCOPES, TARGET_TENANT_SLUG, False, True),
    ("public-event-feedback", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_TOKEN, False, True),
    ("public-event-feedback", _WRITE, PUBLIC_WRITE_SCOPES, TARGET_TENANT_TOKEN, False, True),
    ("public-bookable-space-list", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, True),
    ("public-space-availability", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, True),
    ("public-booking-submit", _WRITE, PUBLIC_WRITE_SCOPES, TARGET_TENANT_SLUG, False, True),
    ("presence-start", _WRITE, PUBLIC_WRITE_SCOPES, TARGET_TENANT_SLUG, False, True),
    ("presence-current", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, True),
    ("presence-end", _WRITE, PUBLIC_WRITE_SCOPES, TARGET_TENANT_SLUG, False, True),
    ("public-membership-request", _WRITE, PUBLIC_WRITE_SCOPES, TARGET_TENANT_SLUG, False, True),
    ("public-membership-admission", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG, False, False),
    ("public-invitation-request", _WRITE, PUBLIC_WRITE_SCOPES, TARGET_TENANT_SLUG, False, True),
    *tuple((name, _WRITE, PUBLIC_WRITE_SCOPES, TARGET_GLOBAL, False, False) for name in (
        "public-hosting-request-submit", "public-hosting-request-open",
        "public-hosting-invitation-resolve", "public-hosting-invitation-submit",
    )),
    (
        "hardware_requests:request-submit", _WRITE, PUBLIC_WRITE_SCOPES,
        TARGET_TENANT_SLUG, False, True,
    ),
    (
        "hardware_requests:request-contact-code", _WRITE, PUBLIC_WRITE_SCOPES,
        TARGET_TENANT_SLUG, False, True,
    ),
    (
        "hardware_requests:public-tool-evidence-url", _WRITE, PUBLIC_WRITE_SCOPES,
        TARGET_TENANT_SLUG, False, True,
    ),
    (
        "hardware_requests:public-tool-checkout", _WRITE, PUBLIC_WRITE_SCOPES,
        TARGET_TENANT_SLUG, False, True,
    ),
    (
        "hardware_requests:public-tool-return", _WRITE, PUBLIC_WRITE_SCOPES,
        TARGET_TENANT_SLUG, False, True,
    ),
    ("hardware_requests:public-tool-checklist", _WRITE, PUBLIC_READ_SCOPES,
     TARGET_TENANT_SLUG, False, False),
    ("public-printer-service-status", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_TOKEN, False, True),
    # Generic token status: same public-read/tenant-token rule, NOT admitted to legacy:v1.
    ("public-machine-service-status", _READ, PUBLIC_READ_SCOPES, TARGET_TENANT_TOKEN, False, False),
    (
        "hardware_requests:request-status", _READ, PUBLIC_READ_SCOPES,
        TARGET_TENANT_TOKEN, False, True,
    ),
)


from .scope_registry_wp4 import definitions as wp4_routes
_ROUTE_DEFINITIONS += wp4_routes(PUBLIC_READ_SCOPES, PUBLIC_WRITE_SCOPES, TARGET_TENANT_SLUG)


from .scope_registry_p2_presence import routes as presence_routes
_ROUTE_DEFINITIONS += presence_routes(PUBLIC_READ_SCOPES, PUBLIC_WRITE_SCOPES, TARGET_TENANT_SLUG)
from .scope_registry_messaging import definitions as messaging_denied_routes
_ROUTE_DEFINITIONS += messaging_denied_routes()


from django.conf import settings
if getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free":
    _ROUTE_DEFINITIONS += (("free_tick:tick", _WRITE, frozenset(), TARGET_GLOBAL, False, False),)
if getattr(settings, "EMAIL_PROVIDER_WEBHOOKS_ENABLED", False):
    _ROUTE_DEFINITIONS += (("email-provider-webhook", _WRITE, frozenset(), TARGET_GLOBAL, False, False),)


def _build_registry():
    registry = {}
    for definition in _ROUTE_DEFINITIONS:
        view_name, methods, scopes, target_mode, tenant_apps_admitted, legacy_v1 = definition
        if target_mode not in TARGET_MODES:
            raise ValueError(f"Unknown API-client target mode: {target_mode}")
        entry = ScopeRegistryEntry(scopes, target_mode, tenant_apps_admitted, legacy_v1)
        for method in methods:
            key = (view_name, method)
            if key in registry:
                raise ValueError(f"Duplicate API-client scope registry key: {key}")
            registry[key] = entry
    from .scope_registry_reads import read_route_entries
    for key, entry in read_route_entries().items():
        if key in registry:
            raise ValueError(f"Duplicate API-client scope registry key: {key}")
        registry[key] = entry
    return MappingProxyType(registry)


from .scope_registry_programme import definitions as programme_definitions
_ROUTE_DEFINITIONS += programme_definitions(
    PUBLIC_READ_SCOPES, PUBLIC_WRITE_SCOPES, TARGET_GLOBAL, TARGET_TENANT_TOKEN,
)
SCOPE_REGISTRY = _build_registry()
