"""Report source prerequisites: module keys, capability keys, or an any-of pair.

`ReportDefinition.required_modules` names what a report reads. Until #97 every entry was
a module key; maintenance and To-Buy are now per-parent capabilities, so an entry may be:

* a module key (`machines`) -- installed and shipped, as before;
* a capability key (`machines.maintenance`) -- effective per `feature_enabled`;
* an any-of pair (`inventory.tobuy|machines.tobuy`) -- one To-Buy list with two
  switches is readable while either parent's switch is on.

Every enforcement site (preview, export, catalog, dashboard, schedules, saved views,
organization and deployment pickers) reads through here, so a report whose source is off
is unavailable the same way everywhere. A switched-off capability source answers 404,
like the folded route it reports on; a missing module keeps its historical 400.
"""

from django.db.models import Q

ANY = "|"


def parts(key):
    return tuple(key.split(ANY)) if ANY in key else (key,)


def is_capability(key):
    return "." in key


def known_source(key):
    from apps.makerspaces.capabilities import FEATURES
    from apps.makerspaces.module_registry import MODULE_KEYS

    return all(part in (FEATURES if is_capability(part) else MODULE_KEYS) for part in parts(key))


def source_enabled(makerspace, key):
    from apps.makerspaces.platform import feature_enabled, module_enabled

    return any(
        feature_enabled(makerspace, part) if is_capability(part) else module_enabled(makerspace, part)
        for part in parts(key)
    )


def require_source(makerspace, key):
    from apps.makerspaces.folded_capabilities import require_any_capability
    from apps.makerspaces.guards import require_module

    if is_capability(key) or ANY in key:
        return require_any_capability(makerspace, parts(key))
    return require_module(makerspace, key)


def source_q(key, prefix=""):
    """SQL twin of `source_enabled` for stored configuration (servability is separate)."""
    from apps.makerspaces.capabilities import feature_required_modules

    combined = Q(pk__in=[])
    for part in parts(key):
        if not is_capability(part):
            combined |= Q(**{f"{prefix}enabled_modules__contains": [part]})
            continue
        term = Q(**{f"{prefix}enabled_features__contains": [part]})
        for module in feature_required_modules(part):
            term &= Q(**{f"{prefix}enabled_modules__contains": [module]})
        combined |= term
    return combined


def filter_sources(queryset, keys, prefix=""):
    for key in keys:
        queryset = queryset.filter(source_q(key, prefix))
    return queryset


def source_app_labels(keys):
    """App labels a deployment tombstone would remove from under these sources."""
    from apps.makerspaces.capabilities import FEATURES

    labels = set()
    for key in keys:
        for part in parts(key):
            definition = FEATURES.get(part) if is_capability(part) else None
            labels.add(definition.app_label if definition and definition.app_label else part)
    return labels
