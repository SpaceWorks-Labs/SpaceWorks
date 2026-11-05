"""Plan usage for the Space Manager (#187A): every limited resource with its level.

``warning`` from 80 % of the limit, ``limit`` at 100 % (where the hard stop refuses the
next create with ``plan_limit_reached``). Uses the same counters as enforcement.
"""

from apps.makerspaces import limits
from apps.makerspaces.limits_core import RESOURCE_LABELS

from .enforcement import MONTHLY_KEYS, MONTHLY_LABELS, NOT_SET, _assignment, monthly_used, plan_limit

WARNING_AT = 80


def level(percent):
    if percent is None:
        return "ok"
    if percent >= 100:
        return "limit"
    return "warning" if percent >= WARNING_AT else "ok"


def _row(key, label, used, limit, unit):
    percent = round(used * 100 / limit, 1) if used is not None and limit else (100.0 if limit == 0 else None)
    return {"key": key, "label": label, "used": used, "limit": limit, "unit": unit,
            "percent": percent, "level": level(percent)}


def plan_usage(makerspace):
    from apps.makerspaces.limits_usage import _COUNTERS
    from apps.space_controls.models import SpaceControlState

    row = _assignment(makerspace)
    keys = sorted(set((row.plan.limits or {}) if row else {}))
    resources = []
    for key in keys:
        if key in MONTHLY_KEYS:
            limit = plan_limit(makerspace, key)
            resources.append(_row(key, MONTHLY_LABELS[key], monthly_used(makerspace, key),
                                  None if limit is NOT_SET else limit, "count"))
            continue
        counter = _COUNTERS.get(key)
        used = counter(makerspace) if counter else None
        resources.append(_row(key, RESOURCE_LABELS.get(key, key), used, limits.resource_limit(makerspace, key),
                              "bytes" if key == "storage" else "count"))
    warnings = [f"{item['label'].capitalize()}: {item['percent']:.0f}% of the plan is used."
                for item in resources if item["level"] != "ok"]
    state = SpaceControlState.objects.filter(makerspace=makerspace).first()
    return {
        "plan": {"key": row.plan.key, "name": row.plan.name, "description": row.plan.description} if row else None,
        "trial_ends_at": row.trial_ends_at if row else None,
        "read_only_reason": state.read_only_reason if state and state.read_only_at else None,
        "resources": resources,
        "warnings": warnings,
    }
