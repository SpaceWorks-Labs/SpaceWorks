"""Per-domain feature switches and settings: an ADAPTER on the settings-authority layer.

"All role-related things go to the respective manager": the Event Manager decides the
`events.*` switches, the Booking Manager the `bookings.*` ones, and so on, without holding
`manage_makerspace` -- but since #101/#128 C-11 only while the Space Manager has granted
them that module (`settings_authority`), and never past a Space Manager lock. The fixed
exception (C-11d) lets the Inventory Manager change rental timing without a grant.

This module decides which keys a domain owns, asks `assert_setting_write` about every key
a request actually changes (refusing the whole request if any is refused, before writing
anything), merges them into the stored list under the row lock, and hands the result to
the one settings write path (`setup_settings.save_space` -> `MakerspaceSerializer`), so
capability prerequisites and per-field validation run as for the full makerspace PATCH.
Each changed key is audited as `settings.changed` with the authority it was made under.

What a domain deliberately does NOT own:

* `enabled_modules` -- modules switch through `module_install` (#128 C-10).
* `payments.*` and `charges.*` -- money owed and the online rail are a finance decision,
  Space-Manager-only and never delegable, even when parented to that domain's module.
* Keys under another prefix (`reports.event_pdf`, `notifications.delegated_recipients`)
  belong to the reports and notifications areas, which have no domain manager.
* Reserved switches with no surface yet (`frontend_exposed=False`, e.g. L16's repairs).
"""

from dataclasses import dataclass

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.accounts.rbac_actions import Action

from .capabilities import FEATURE_DEFINITIONS, feature_required_modules
from .module_registry import module_available


@dataclass(frozen=True)
class Domain:
    action: str
    prefixes: tuple[str, ...]
    settings: tuple[str, ...]


DOMAINS = {
    "events": Domain(
        Action.MANAGE_EVENTS, ("events.",),
        ("event_default_registration_audience", "event_reminder_lead_hours"),
    ),
    "bookings": Domain(
        Action.MANAGE_BOOKINGS, ("bookings.",),
        ("booking_requester_notifications_enabled", "booking_reminder_lead_hours"),
    ),
    "machines": Domain(
        Action.MANAGE_MACHINES, ("machines.", "maintenance."),
        ("filament_low_stock_threshold_grams",),
    ),
    "inventory": Domain(
        Action.EDIT_INVENTORY, ("loans.", "inventory.", "stocktake."), (),
    ),
    # L22 (#137): the Shop Manager decides the shop's own switches without a grant.
    "shop": Domain(Action.MANAGE_SHOP, ("shop.",), ()),
}
SETTING_FIELDS = tuple(dict.fromkeys(
    field for domain in DOMAINS.values() for field in domain.settings
))


def feature_keys(domain):
    """The domain's feature keys, in registry order."""
    prefixes = DOMAINS[domain].prefixes
    return tuple(
        definition.key for definition in FEATURE_DEFINITIONS
        if definition.key.startswith(prefixes) and definition.frontend_exposed
    )


def can_edit(actor, makerspace, domain):
    """Whether the actor may change this domain's settings in general (grant or Space Manager).

    Per-key answers -- locks, the rental-timing exception -- are in `key_permissions`.
    """
    from .settings_authority import is_space_manager, live_grant, machine_scope_covers_all

    if is_space_manager(actor, makerspace):
        return True
    if live_grant(makerspace, domain, actor) is None:
        return False
    return domain != "machines" or machine_scope_covers_all(actor, makerspace)


def key_permissions(actor, makerspace, domain):
    """`{key: {"editable": bool, "locked": bool}}` for every switch and setting of a domain."""
    from .models_settings_authority import ModuleSettingLock
    from .settings_authority import decide, live_grant

    locks = {row.setting_key: row for row in ModuleSettingLock.objects.filter(
        makerspace=makerspace, released_at__isnull=True)}
    grant = live_grant(makerspace, domain, actor)
    keys = (*feature_keys(domain), *DOMAINS[domain].settings)
    return {key: {"editable": decide(actor, makerspace, domain, key, lock=locks.get(key), grant=grant).allowed,
                  "locked": key in locks} for key in keys}


def describe(makerspace, domain, editable, permissions=None):
    """Read model for one domain: its switches, their availability, and its settings."""
    from apps.separability.registry import runtime_active

    enabled = set(makerspace.enabled_features or [])
    modules = set(makerspace.enabled_modules or [])
    by_key = {definition.key: definition for definition in FEATURE_DEFINITIONS}
    permissions = permissions or {}
    default = {"editable": editable, "locked": False}
    features = []
    for key in feature_keys(domain):
        definition = by_key[key]
        allowed = permissions.get(key, default)
        features.append({
            "key": key,
            "label": definition.label,
            "description": definition.description,
            "parent_module": definition.parent_module,
            "requires_features": list(definition.requires_features),
            "enabled": key in enabled,
            "available": all(
                module in modules and module_available(module)
                for module in feature_required_modules(key)
            ) and (definition.app_label is None or runtime_active(definition.app_label)),
            "editable": allowed["editable"],
            "locked": allowed["locked"],
        })
    return {
        "domain": domain,
        "editable": editable,
        "features": features,
        "settings": {
            field: getattr(makerspace, field) for field in DOMAINS[domain].settings
        },
        "setting_permissions": {
            field: permissions.get(field, default) for field in DOMAINS[domain].settings
        },
    }


def apply_domain_settings(actor, makerspace, domain, features, settings):
    """Toggle this domain's keys and write its settings through the shared serializer."""
    spec = DOMAINS[domain]
    owned = set(feature_keys(domain))
    problems = {}
    foreign = sorted(set(features) - owned)
    if foreign:
        problems["features"] = {key: f"Not a {domain} setting." for key in foreign}
    foreign = sorted(set(settings) - set(spec.settings))
    if foreign:
        problems["settings"] = {key: f"Not a {domain} setting." for key in foreign}
    if problems:
        raise ValidationError(problems)

    from .models import Makerspace
    from .setup_settings import save_space

    from .settings_authority import assert_setting_write, record_change

    with transaction.atomic():
        # Merge under the row lock: another domain's manager may be toggling their own
        # keys concurrently, and a read-modify-write outside it would lose their change.
        locked = Makerspace.objects.select_for_update().get(pk=makerspace.pk)
        stored = set(locked.enabled_features or [])
        changes = {key: (key in stored, bool(on)) for key, on in features.items()
                   if (key in stored) != bool(on)}
        changes.update({field: (getattr(locked, field), value) for field, value in settings.items()
                        if getattr(locked, field) != value})
        # Every changed key is authorized before anything is written (#101).
        decisions = {key: assert_setting_write(actor, locked, domain, key) for key in changes}
        values = dict(settings)
        if features:
            merged = set(stored)
            for key, on in features.items():
                if on:
                    merged.add(key)
                else:
                    merged.discard(key)
            values["enabled_features"] = sorted(merged)
        if not values:
            return locked
        try:
            saved = save_space(actor, locked, values)
        except ValidationError as exc:
            raise ValidationError(_nest_errors(exc.detail)) from exc
        for key, (before, after) in changes.items():
            record_change(actor, saved, domain, key, _plain(before), _plain(after), decisions[key])
        return saved


def _plain(value):
    """Audit meta takes JSON: decimals and other scalars are stored as strings."""
    return value if isinstance(value, (bool, int, str, list, type(None))) else str(value)


def _nest_errors(detail):
    """Report serializer errors under the request's own `features`/`settings` keys."""
    if not isinstance(detail, dict):
        return detail
    nested = {}
    for field, messages in detail.items():
        if field == "enabled_features":
            nested["features"] = messages
        elif field in SETTING_FIELDS:
            nested.setdefault("settings", {})[field] = messages
        else:
            nested[field] = messages
    return nested
