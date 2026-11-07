"""Installer areas are bundles over the module and feature registries, not new gates."""
from .capabilities import FEATURES, prune_features
from .module_registry import core_module_keys, with_dependencies
from .capability_definitions_r2_l17 import RESERVED_KEYS

AREAS = {
    "inventory": ("public_inventory", "request_workflow", "staff_admin", "scanner",
                  "evidence_uploads", "qr_management", "guest_handover", "asset_units",
                  "containers", "bulk_import", "stock_transfers", "qr_print_batches",
                  "stocktake", "devices"),
    "machines": ("machines", "machine_service", "printing"),
    "events": ("events",),
    "bookings": ("bookings",),
    "membership": ("membership", "mobile"),
    "payments": ("payments",),
    "reports": ("reports",),
    "chat": ("telegram", "slack", "mattermost", "discord", "webhook"),
}
ALWAYS_MODULES = {"notifications", "email", "member_accounts"}
ALWAYS_FEATURES = {"billing.reminders", "charges.enabled", "billing.documents",
                   "staff.invitations", "presence.geofence", "ui.delight", "ui.easter_eggs",
                   "platform.help_centre", "charges.donations"}
# The inventory family is parentless, so the area names its switches; To-Buy and warranty
# replace the retired `procurement` module this area used to install (#97, C-9).
INVENTORY_FEATURES = {"inventory.self_checkout", "inventory.kiosk", "inventory.tobuy", "inventory.warranty"}
EXPLICIT_OPT_IN_FEATURES = frozenset({
    "events.hackathons", "events.mentoring", "events.mentor_rounds",
    "events.volunteering", "events.project_gallery", "events.pairwise_judging",
    *RESERVED_KEYS,
})


def modules_for(areas):
    return with_dependencies(core_module_keys() | ALWAYS_MODULES | {
        module for area in areas for module in AREAS[area]
    })


def features_for(areas, modules=None):
    """Bundle ordinary children; programme features require an explicit choice."""
    modules = set(modules if modules is not None else modules_for(areas))
    parents = ALWAYS_MODULES | {module for area in areas for module in AREAS[area]}
    features = ALWAYS_FEATURES | {
        key for key, definition in FEATURES.items() if definition.parent_module in parents
    }
    features -= EXPLICIT_OPT_IN_FEATURES
    if "inventory" in areas:
        features |= INVENTORY_FEATURES
    else:
        # Core is installed even when lending is hidden. It must not enable loans.
        features -= {key for key in features if key.startswith(("loans.", "inventory."))}
        features -= {"charges.loans", "payments.loans"}
    supported, _ = prune_features(features, modules)
    return sorted(supported)


def edition_for(areas, organization=False):
    if organization:
        return "organization"
    primary = set(areas) - {"membership", "payments", "reports", "chat"}
    return next(iter(primary)) if primary in ({"events"}, {"bookings"}) else "makerspace"


def area_status(space):
    installed = set(space.enabled_modules or [])
    features = set(space.enabled_features or [])
    result = {}
    for key, modules in AREAS.items():
        optional = set(modules) - core_module_keys()
        count = len(optional & installed)
        state = "on" if count == len(optional) else "partial" if count else "off"
        if key == "inventory":
            if "loans.enabled" not in features:
                state = "partial" if count else "off"
            elif not count:
                state = "partial"
        result[key] = state
    return result


def active_areas(space):
    """Existing domain configuration survives completing a partial module bundle."""
    modules = set(space.enabled_modules or [])
    anchors = {"machines": "machines", "events": "events", "bookings": "bookings",
               "membership": "membership", "payments": "payments", "reports": "reports"}
    return {"inventory": "loans.enabled" in (space.enabled_features or []),
            **{area: module in modules for area, module in anchors.items()},
            "chat": bool(set(AREAS["chat"]) & modules)}
