"""Which spaces a scheduled task may touch, by the module/capability it serves (#183B).

A switched-off module or capability runs no scheduled work; its rows are kept and the
work resumes when the switch comes back on. Scheduled tasks narrow their querysets with
`live_space_ids(...)` instead of a raw `enabled_modules__contains` /
`enabled_features__contains` filter, because a raw JSON contains misses what the registry
helpers know: a tombstoned app (`module_available`), a capability's parent module and
required modules, and the `loans.enabled` master (`configuration_feature_enabled`).

This answers the CONFIGURATION question only. Servability stays with the caller's
existing boundary (`rbac.scope_for_scheduled_work` and the tenant write gate), which
deliberately keeps frozen tenants in the scan so the gate can count their skips.

A source is a module key, a capability key (dotted), or `a|b` (on while either is on);
a tuple of sources must all be on. `tests/modules/test_scheduled_task_sources.py` maps
every scheduled task to its source, or to an explicit platform-level exemption.
"""
from apps.makerspaces.capability_eligibility import configuration_feature_enabled
from apps.makerspaces.module_registry import module_available


def source_configured(makerspace, source):
    """True while `source` is switched on for this space (configuration, not servability)."""
    if isinstance(source, tuple):
        return all(source_configured(makerspace, part) for part in source)
    modules = set(makerspace.enabled_modules or [])
    for part in source.split("|"):
        if "." in part:
            if configuration_feature_enabled(makerspace, part):
                return True
        elif part in modules and module_available(part):
            return True
    return False


def live_space_ids(source, queryset=None):
    """Ids of the spaces (optionally within `queryset`) where `source` is switched on."""
    from apps.makerspaces.models import Makerspace

    rows = (queryset if queryset is not None else Makerspace.objects.all()).only(
        "pk", "enabled_modules", "enabled_features",
    )
    return {row.pk for row in rows.iterator() if source_configured(row, source)}
