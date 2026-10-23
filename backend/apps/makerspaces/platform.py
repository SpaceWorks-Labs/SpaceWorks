from urllib.parse import urlencode, urlparse

from django.conf import settings

from apps.inventory import public_image_storage
from apps.integrations.email import email_enabled
from apps.makerspaces.models import Makerspace, default_branding_config
from apps.makerspaces.theme_validation import public_theme_config
from apps.makerspaces.servability import is_servable, servable_queryset
from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.capability_eligibility import configuration_feature_enabled
from apps.makerspaces.module_registry import is_frontend_exposed, module_available, module_workflows
from apps.separability.registry import runtime_active
from apps.makerspaces.loan_visibility import LOAN_MODULES

# Derived from the module registry, which also decides frontend exposure: an
# internal master switch declares frontend_exposed=False and is dropped from both
# the bootstrap `modules` list and these workflows.
MODULE_WORKFLOWS = module_workflows()

FEATURE_WORKFLOWS = {
    "inventory.self_checkout": ["self_checkout", "self_return"],
    "inventory.kiosk": ["kiosk", "kiosk_scanner"],
}


def origin_to_hostname(origin):
    if not origin:
        return ""
    parsed = urlparse(origin if "://" in origin else f"//{origin}")
    return (parsed.hostname or "").lower()


def makerspace_staff_origins(makerspace):
    origins = set(settings.PLATFORM_STAFF_ORIGINS)
    if (
        makerspace.frontend_domain
        and makerspace.frontend_domain_status == Makerspace.DomainStatus.VERIFIED
    ):
        origins.add(f"https://{makerspace.frontend_domain}")
    return origins


def makerspace_public_origins(makerspace):
    return makerspace_staff_origins(makerspace) | set(makerspace.cors_allowed_origins or [])


def member_area_url(makerspace):
    """Return the canonical member-area URL for a makerspace frontend."""
    if (
        makerspace.frontend_domain
        and makerspace.frontend_domain_status == Makerspace.DomainStatus.VERIFIED
    ):
        return f"https://{makerspace.frontend_domain}/member"
    base = (settings.PUBLIC_APP_BASE_URL or "http://localhost:5000").rstrip("/")
    return f"{base}/m/{makerspace.slug}/member" if base and makerspace.slug else ""


def member_payment_return_url(makerspace):
    """Where a payer lands after checkout, including when the makerspace is archived.

    `member_area_url` sends them to the tenant's own member area, which for an ARCHIVED space
    is a dead end: its custom domain has lost bootstrap and origin trust, and `/m/<slug>/member`
    cannot resolve the tenant either. Returning someone there immediately after they paid
    strands them on a 404 holding a charge they have just settled. The recovery route is
    authentication-only and always lives on the central app, so it is reachable regardless of
    what happened to the tenant's domain.
    """
    if not is_servable(makerspace):
        base = (settings.PUBLIC_APP_BASE_URL or "http://localhost:5000").rstrip("/")
        return f"{base}/member/archived" if base else ""
    return member_area_url(makerspace)


def staff_payment_settings_url(makerspace=None, *, outcome):
    """Return a trusted staff settings URL without accepting browser input."""
    verified_domain = (
        makerspace is not None
        and makerspace.frontend_domain
        and makerspace.frontend_domain_status == Makerspace.DomainStatus.VERIFIED
    )
    if verified_domain:
        base = f"https://{makerspace.frontend_domain}"
    else:
        base = (settings.PUBLIC_APP_BASE_URL or "http://localhost:5000").rstrip("/")
    path = (
        "/admin/settings"
        if verified_domain
        else f"/m/{makerspace.slug}/admin/settings"
        if makerspace is not None and makerspace.slug
        else "/admin/settings"
    )
    return f"{base}{path}?{urlencode({'stripe_connect': outcome})}"


def resolve_frontend(*, tenant=None, slug=None, origin=None, host=None):
    if tenant:
        return servable_queryset(Makerspace.objects.filter(
            public_code__iexact=tenant,
        )).first()
    if slug:
        return servable_queryset(Makerspace.objects.filter(
            slug=slug,
        )).first()
    hostname = origin_to_hostname(origin) or origin_to_hostname(host)
    if hostname:
        return servable_queryset(Makerspace.objects.filter(
            frontend_domain__iexact=hostname,
        )).first()
    return None


def module_enabled(makerspace, module_key):
    # Two independent switches, both of which must be on: the tenant enabled the
    # module, and this deployment still ships the app that implements it. Merging
    # them here rather than at each call site is what makes tombstoning safe -- a
    # guard added in future code inherits the check without knowing it exists.
    #
    # `allow_archived=True` is deliberate: this answers a CAPABILITY question, not a
    # liveness one. Letting archival answer it here would tell every caller that an
    # archived tenant's modules are "disabled", which is both false and a change to
    # shipped behaviour -- an archived makerspace is meant to fail its own archived
    # checks with PermissionDenied, not to report that maintenance was uninstalled.
    # The IMPORTING/ABORTED states are new, so refusing them here adds defence in
    # depth behind the boundary guards without altering any existing contract.
    return (
        is_servable(makerspace, allow_archived=True)
        and module_key in set(makerspace.enabled_modules or [])
        and module_available(module_key)
    )


def available_modules(makerspace):
    """The tenant's stored module keys, minus any whose owning app is tombstoned.

    This is what an API tells a client it can use. The raw field stays intact for
    `/control/` and for `module_install`, which must show and edit what is stored,
    not what happens to be reachable today.
    """
    from apps.makerspaces.editions import hidden_module_keys

    hidden = hidden_module_keys()
    return sorted(
        key
        for key in set(makerspace.enabled_modules or [])
        if module_available(key) and key not in hidden
    )


def feature_enabled(makerspace, key):
    # See `module_enabled`: capability, not liveness, so archival is left to the
    # archived checks and only the new lifecycle states fail closed here.
    if not is_servable(makerspace, allow_archived=True):
        return False
    return configuration_feature_enabled(makerspace, key)

def bootstrap_payload(makerspace):
    from apps.makerspaces.editions import current_edition
    from apps.integrations.messaging.resolver import resolve_sender

    modules = sorted(key for key in available_modules(makerspace) if is_frontend_exposed(key))
    if not feature_enabled(makerspace, "loans.enabled"):
        modules = [key for key in modules if key not in LOAN_MODULES]
    features = sorted(key for key, definition in FEATURES.items() if definition.frontend_exposed and feature_enabled(makerspace, key))
    theme = public_theme_config(makerspace.theme_config)
    logo_url = public_image_storage.public_url(makerspace.logo_key) or theme.get("logo_url") or ""
    cover_image_url = public_image_storage.public_url(makerspace.cover_image_key) or ""
    branding = default_branding_config()
    branding.update(makerspace.branding_config or {})
    if not branding.get("display_name"):
        branding["display_name"] = makerspace.name
    workflows = sorted({
        workflow for module in modules for workflow in MODULE_WORKFLOWS.get(module, [])
    } | {
        workflow for feature in features for workflow in FEATURE_WORKFLOWS.get(feature, [])
    })
    if not feature_enabled(makerspace, "loans.enabled"):
        workflows = [key for key in workflows if key not in {"staff_inventory", "staff_requests"}]
    makerspace_payload = {
        "id": makerspace.id,
        "name": makerspace.name,
        "slug": makerspace.slug,
        "public_code": makerspace.public_code,
        "location": makerspace.location,
        "timezone": makerspace.timezone,
        "opening_hours": makerspace.opening_hours,
        "map_url": makerspace.map_url,
        "logo_url": logo_url,
        "cover_image_url": cover_image_url,
        "public_stats_enabled": makerspace.public_stats_enabled,
        "public_site_enabled": makerspace.public_site_enabled,
        "public_inventory_enabled": makerspace.public_inventory_enabled,
        "public_landing_page": makerspace.public_landing_page,
        "membership_policy": makerspace.membership_policy,
    }
    # Emitted ONLY for a space without member accounts (#80), so every other deployment
    # keeps a byte-for-byte identical payload; absent means "sign in to request". The
    # public form needs it to ask for name, phone, email and the email code instead.
    from apps.makerspaces.request_access import CONTACT, effective_policy

    if effective_policy(makerspace) == CONTACT:
        makerspace_payload["request_access"] = CONTACT
    # Advisory geofence: expose the flag ONLY when configured AND the feature is on, so
    # dormant/self-host bootstrap payloads stay byte-for-byte unchanged (self-host
    # invariant) and a disabled feature cannot leave the client asking for coordinates
    # the backend will ignore.
    # `presence.geofence` is a standalone feature (parent_module=None), so no module
    # key expresses that the app is gone -- the availability check has to be explicit
    # or a tombstoned deployment would still ask the browser for coordinates.
    if (
        makerspace.geofence_effective
        and feature_enabled(makerspace, "presence.geofence")
        and runtime_active("presence")
    ):
        makerspace_payload["geofence_enabled"] = True
    return {
        "makerspace": makerspace_payload,
        "frontend": {
            "type": "makerspace",
            "hostname": makerspace.frontend_domain or "",
            "allowed_origins": sorted(makerspace_public_origins(makerspace)),
        },
        "modules": modules,
        "edition": current_edition().key,
        "features": features,
        "workflows": workflows,
        "theme": theme,
        "branding": branding,
        "email_enabled": email_enabled(),
        "messaging": {channel: module_enabled(makerspace, channel) and resolve_sender(makerspace, channel) is not None
                      for channel in ("sms", "whatsapp")},
        "public_api": {
            "base_url": "/api/v1",
            "publishable_key": makerspace.public_api_key,
            "inventory_path": f"/api/v1/public/{makerspace.slug}/inventory/",
        },
    }
