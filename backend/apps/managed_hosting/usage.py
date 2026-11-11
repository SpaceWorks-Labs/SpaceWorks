"""Plan usage for the Space Manager (#187A): every limited resource with its level.

``warning`` from 80 % of the limit, ``limit`` at 100 % (where the hard stop refuses the
next create with ``plan_limit_reached``). Uses the same counters as enforcement.
"""

from apps.makerspaces import limits
from apps.makerspaces.limits_core import RESOURCE_LABELS

from .enforcement import MONTHLY_KEYS, MONTHLY_LABELS, NOT_SET, _assignment, monthly_used, plan_limit
from .limit_catalogue import NEW_KEYS, effective_limit, label_of, registry_keys, unit_of, used_of

WARNING_AT = 80


def level(percent):
    if percent is None:
        return "ok"
    if percent >= 100:
        return "limit"
    return "warning" if percent >= WARNING_AT else "ok"


def _row(key, label, used, limit, unit):
    percent = round(used * 100 / limit, 1) if used is not None and limit else (100.0 if limit == 0 else None)
    from apps.makerspaces.limit_registry import area_of
    return {"key": key, "label": label, "used": used, "limit": limit, "unit": unit, "area": area_of(key),
            "percent": percent, "level": level(percent)}


def platform_resources(makerspace):
    """Platform-credential rows (every space; limit null = unlimited) with the usual warning level."""
    from .platform_limits import usage_rows
    return [{**row, "unit": "count", "level": level(row["percent"])} for row in usage_rows(makerspace)]


def _extras(makerspace):
    """Read-only for the Space Manager: the superadmin's monthly quotas and the five platform-fallback switches."""
    from .platform_switch import platform_switches
    from .space_quotas import usage_rows
    return {"space_quota_resources": usage_rows(makerspace), "platform_switches": platform_switches(makerspace)}


def _override_resources(makerspace):
    """An own space has no plan, but a limit the superadmin SET on it still shows its usage."""
    from apps.makerspaces.limits_usage import _COUNTERS
    rows = []
    set_keys = set(makerspace.resource_limit_overrides or {})
    for key in (k for k in registry_keys() if k in set_keys):  # every registry key, grouped by area (#261)
        limit = effective_limit(makerspace, key)
        counter = _COUNTERS.get(key)
        if limit is None:
            continue
        if key in NEW_KEYS:
            rows.append(_row(key, label_of(key), used_of(makerspace, key), limit, unit_of(key)))
        elif counter:
            rows.append(_row(key, RESOURCE_LABELS.get(key, key), counter(makerspace), limit, unit_of(key)))
    return rows


def plan_usage(makerspace):
    from apps.makerspaces.limits_usage import _COUNTERS
    from apps.space_controls.models import SpaceControlState

    from .hosting_type import is_hosted

    state = SpaceControlState.objects.filter(makerspace=makerspace).first()
    read_only = state.read_only_reason if state and state.read_only_at else None
    if not is_hosted(makerspace):
        # Decision 236: an own space has no plan and no limits; the page says "Unlimited (own space)".
        return {"plan": None, "trial_ends_at": None, "read_only_reason": read_only,
                "resources": _override_resources(makerspace), "warnings": [], "hosted": False,
                "platform_resources": platform_resources(makerspace), **_extras(makerspace)}
    row = _assignment(makerspace)
    plan_keys = set((row.plan.limits or {}) if row else {})
    keys = [key for key in registry_keys() + sorted(MONTHLY_KEYS - set(registry_keys())) if key in plan_keys]
    resources = []
    for key in keys:
        if key in MONTHLY_KEYS and key not in NEW_KEYS:
            limit = plan_limit(makerspace, key)
            resources.append(_row(key, MONTHLY_LABELS[key], monthly_used(makerspace, key),
                                  None if limit is NOT_SET else limit, "count"))
            continue
        if key in NEW_KEYS:
            resources.append(_row(key, label_of(key), used_of(makerspace, key), effective_limit(makerspace, key),
                                  unit_of(key)))
            continue
        counter = _COUNTERS.get(key)
        used = counter(makerspace) if counter else None
        resources.append(_row(key, RESOURCE_LABELS.get(key, key), used, limits.resource_limit(makerspace, key),
                              unit_of(key)))
    warnings = [f"{item['label'].capitalize()}: {item['percent']:.0f}% of the plan is used."
                for item in resources if item["level"] != "ok"]
    return {
        "plan": {"key": row.plan.key, "name": row.plan.name, "description": row.plan.description} if row else None,
        "trial_ends_at": row.trial_ends_at if row else None,
        "read_only_reason": read_only,
        "resources": resources,
        "warnings": warnings,
        "hosted": True,
        "platform_resources": platform_resources(makerspace),
        **_extras(makerspace),
    }
