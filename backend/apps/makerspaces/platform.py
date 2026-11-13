from apps.inventory import public_image_storage
from apps.integrations.email import email_enabled
from apps.makerspaces.models import default_branding_config
from apps.makerspaces.theme_validation import public_theme_config
from apps.makerspaces.servability import is_servable
from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.capability_eligibility import configuration_feature_enabled
from apps.makerspaces.module_aliases import canonical_module_key, canonical_module_keys
from apps.makerspaces.module_registry import is_frontend_exposed, module_available, module_workflows
from apps.separability.registry import runtime_active
from apps.makerspaces.loan_visibility import LOAN_MODULES, INVENTORY_ONLY_MODULES
# Frontend URL and origin helpers live in `platform_urls.py`; re-exported so callers keep importing them here.
from apps.makerspaces.platform_urls import (  # noqa: F401
    SETTINGS_FIX_PATHS,
    _frontend_rows,
    makerspace_public_origins,
    makerspace_staff_origins,
    member_area_url,
    member_payment_return_url,
    origin_to_hostname,
    paused_frontend,
    resolve_frontend,
    staff_payment_settings_url,
)


def inventory_master_allows(makerspace, module_key):
    """Inventory-only modules answer off while the Inventory switch is off (decision 254)."""
    return module_key not in INVENTORY_ONLY_MODULES or configuration_feature_enabled(makerspace, "loans.enabled")

# Derived from the module registry, which also decides frontend exposure: an
# internal master switch declares frontend_exposed=False and is dropped from both
# the bootstrap `modules` list and these workflows.
MODULE_WORKFLOWS = module_workflows()

# Events and Bookings declare no registry workflow, so an events-only or bookings-only space (decision 254:
# every area combination has something to show on the public site) would otherwise publish none.
MODULE_AREA_WORKFLOWS = {"events": ["events"], "bookings": ["bookings"]}

FEATURE_WORKFLOWS = {
    "inventory.self_checkout": ["self_checkout", "self_return"],
    "inventory.kiosk": ["kiosk", "kiosk_scanner"],
    # The retired `maintenance`/`procurement` module keys' workflows, now per parent (#97).
    "machines.maintenance": ["maintenance"],
    "machines.tobuy": ["procurement"],
    "inventory.tobuy": ["procurement"],
}


def module_enabled(makerspace, module_key):
    # Two independent switches, both of which must be on: the tenant enabled the
    # module, and this deployment still ships the app that implements it. Merging
    # them here rather than at each call site is what makes tombstoning safe -- a
    # guard added in future code inherits the check without knowing it exists.
    # `allow_archived=True` is deliberate: this answers a CAPABILITY question, not a
    # liveness one. Letting archival answer it here would tell every caller that an
    # archived tenant's modules are "disabled", which is both false and a change to
    # shipped behaviour -- an archived makerspace is meant to fail its own archived
    # checks with PermissionDenied, not to report that maintenance was uninstalled.
    # The IMPORTING/ABORTED states are new, so refusing them here adds defence in
    # depth behind the boundary guards. Retired keys read as their live key (340b).
    module_key = canonical_module_key(module_key)
    return (
        is_servable(makerspace, allow_archived=True)
        and module_key in set(canonical_module_keys(makerspace.enabled_modules))
        and module_available(module_key)
        and inventory_master_allows(makerspace, module_key)
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
        for key in set(canonical_module_keys(makerspace.enabled_modules))
        if module_available(key) and key not in hidden
    )


def feature_enabled(makerspace, key):
    # See `module_enabled`: capability, not liveness, so archival is left to the
    # archived checks and only the new lifecycle states fail closed here.
    if not is_servable(makerspace, allow_archived=True):
        return False
    return configuration_feature_enabled(makerspace, key)

def bootstrap_payload(makerspace):
    from config.locale_registry import locale_list_payload

    from apps.makerspaces.editions import current_edition
    from apps.integrations.messaging.resolver import resolve_sender
    from apps.payments.availability import charges_tracked

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
        workflow for module in modules
        for workflow in [*MODULE_WORKFLOWS.get(module, []), *MODULE_AREA_WORKFLOWS.get(module, [])]
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
    # Decision 295: kind keys only for an organization workspace (byte-identical otherwise).
    from apps.makerspaces.space_kind import bootstrap_kind_payload

    makerspace_payload.update(bootstrap_kind_payload(makerspace))
    # Emitted ONLY for a space without member accounts (#80), so every other deployment
    # keeps a byte-for-byte identical payload; absent means "sign in to request". The
    # public form needs it to ask for name, phone, email and the email code instead.
    from apps.makerspaces.request_access import CONTACT, effective_policy

    if effective_policy(makerspace) == CONTACT:
        makerspace_payload["request_access"] = CONTACT
    # #77: emitted only while the switch is on and a notice is set, so every other
    # space keeps a byte-for-byte identical payload.
    from apps.makerspaces.closed_notice import public_notice

    notice = public_notice(makerspace)
    if notice:
        makerspace_payload["closed_notice"] = notice
    # P3-4: emitted only for a space that records opening hours (byte-identical otherwise).
    from apps.makerspaces.opening_hours import has_hours

    if has_hours(makerspace):
        from apps.makerspaces.open_status import open_status

        makerspace_payload["open_status"] = open_status(makerspace)
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
    # Decision 242(m): the public Donate entry, emitted only for a non-profit taking gifts.
    from apps.payments.donations.nonprofit import donate_entry_enabled

    if donate_entry_enabled(makerspace):
        makerspace_payload["donate_enabled"] = True
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
        "charges_tracked": charges_tracked(makerspace),
        "workflows": workflows,
        "theme": theme,
        "branding": branding,
        "email_enabled": email_enabled(),
        # Phase 8 i18n: the space's default language and what the switcher may offer.
        "default_locale": makerspace.default_locale,
        "supported_locales": locale_list_payload(),
        "messaging": {channel: module_enabled(makerspace, channel) and resolve_sender(makerspace, channel) is not None
                      for channel in ("sms", "whatsapp")},
        "public_api": {
            "base_url": "/api/v1",
            "publishable_key": makerspace.public_api_key,
            "inventory_path": f"/api/v1/public/{makerspace.slug}/inventory/",
        },
    }
