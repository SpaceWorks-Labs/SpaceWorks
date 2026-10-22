"""Per-domain feature switches and settings, editable by that domain's own manager.

"All role-related things go to the respective manager": the Event Manager decides the
`events.*` switches, the Booking Manager the `bookings.*` ones, and so on, without holding
`manage_makerspace`. This module is only a narrowing ADAPTER in front of the one settings
write path (`setup_settings.save_space` -> `MakerspaceSerializer`): it decides which keys a
domain owns, merges them into the stored list under the row lock, and hands the result to
the serializer. Capability prerequisites, module checks and per-field validation therefore
run exactly as they do for the full makerspace PATCH, and the audit rows are the same
`makerspace.updated` / `makerspace.features_changed` entries.

What a domain deliberately does NOT own:

* `enabled_modules` -- installing a module stays superadmin-only, everywhere.
* `payments.*` and `charges.*` -- money owed and the online rail are a finance decision
  (`view_finance` / `record_payment` / `manage_makerspace`), not a domain one, even when
  the key is parented to that domain's module.
* Keys under another prefix (`reports.event_pdf`, `notifications.delegated_recipients`)
  belong to the reports and notifications areas, which have no domain manager.
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
}
SETTING_FIELDS = tuple(dict.fromkeys(
    field for domain in DOMAINS.values() for field in domain.settings
))


def feature_keys(domain):
    """The domain's feature keys, in registry order."""
    prefixes = DOMAINS[domain].prefixes
    return tuple(
        definition.key for definition in FEATURE_DEFINITIONS
        if definition.key.startswith(prefixes)
    )


def can_edit(actor, makerspace, domain):
    """Whether an actor who already holds the domain action may WRITE its settings.

    Every machine-domain key and setting is tenant-wide: certification gating, public
    machine details, maintenance meters and the filament threshold apply to every machine
    in the space. A Machine Manager's reach is limited to their assigned types, so letting
    a type-scoped manager flip one would change machines they cannot otherwise touch. They
    may write only while no machine outside their types exists (nothing outside their
    reach is affected); otherwise it stays with the Space Manager. Reads are not narrowed.
    """
    if domain != "machines":
        return True
    from apps.machines.models import Machine
    from apps.machines.role_scope import EXEMPT, manage_scope_for

    scope = manage_scope_for(actor, makerspace.pk)
    if scope is EXEMPT:
        return True
    type_ids, _machine_ids = scope
    return not Machine.objects.filter(makerspace=makerspace).exclude(
        machine_type_id__in=type_ids,
    ).exists()


def describe(makerspace, domain, editable):
    """Read model for one domain: its switches, their availability, and its settings."""
    enabled = set(makerspace.enabled_features or [])
    modules = set(makerspace.enabled_modules or [])
    by_key = {definition.key: definition for definition in FEATURE_DEFINITIONS}
    features = []
    for key in feature_keys(domain):
        definition = by_key[key]
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
            ),
        })
    return {
        "domain": domain,
        "editable": editable,
        "features": features,
        "settings": {
            field: getattr(makerspace, field) for field in DOMAINS[domain].settings
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

    with transaction.atomic():
        # Merge under the row lock: another domain's manager may be toggling their own
        # keys concurrently, and a read-modify-write outside it would lose their change.
        locked = Makerspace.objects.select_for_update().get(pk=makerspace.pk)
        values = dict(settings)
        if features:
            merged = set(locked.enabled_features or [])
            for key, on in features.items():
                if on:
                    merged.add(key)
                else:
                    merged.discard(key)
            values["enabled_features"] = sorted(merged)
        if not values:
            return locked
        try:
            return save_space(actor, locked, values)
        except ValidationError as exc:
            raise ValidationError(_nest_errors(exc.detail)) from exc


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
