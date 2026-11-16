"""One row per countable limit key for a space: what applies, where it comes from, current use (decision 328a).

Feeds the threshold sweep and the Space Manager's "Limits and usage" view. Resolution is the single order used by
enforcement: the space's override, a hosted space's plan, the platform default, then no limit. Rows use the
counters enforcement uses; a counter that fails answers ``used: None`` so one bad counter cannot hide the rest.
"""
from apps.makerspaces.limit_modules import group_of, module_of
from apps.makerspaces.limits_core import CAP_LIMIT_KEYS, NUMERIC_LIMIT_KEYS

from .enforcement import NOT_SET, plan_limit
from .limit_catalogue import effective_limit, label_of, registry_keys, unit_of, used_of
from .limit_defaults import platform_default
from .usage import level


def source_of(makerspace, key):
    """`override`, `plan`, `default` (the platform default) or `unlimited`."""
    if key in (makerspace.resource_limit_overrides or {}):
        return "override"
    if plan_limit(makerspace, key) is not NOT_SET:
        return "plan"
    return "default" if platform_default(key) is not None else "unlimited"


def _used(makerspace, key, daily):
    if key in CAP_LIMIT_KEYS:
        return None  # a per-file cap: nothing is used up
    if key in NUMERIC_LIMIT_KEYS:
        from apps.makerspaces.limits_usage import _COUNTERS
        counter = _COUNTERS.get(key)
        return counter(makerspace) if counter else daily().get(key, 0)
    return used_of(makerspace, key)


def percent_of(used, limit):
    if limit is None or used is None:
        return None
    return 100.0 if limit <= 0 else round(used * 100 / limit, 1)


def overview_rows(makerspace, *, limited_only=False):
    cache = {}

    def daily():
        if "d" not in cache:
            from .limits_console import _daily_notifications
            cache["d"] = _daily_notifications(makerspace)
        return cache["d"]

    rows = []
    for key in registry_keys():
        limit = effective_limit(makerspace, key)
        if limited_only and limit is None:
            continue
        try:
            used = None if limit is None else _used(makerspace, key, daily)
        except Exception:  # noqa: BLE001 - a counter of a tombstoned app must not break the page
            used = None
        percent = percent_of(used, limit)
        rows.append({"key": key, "label": label_of(key), "unit": unit_of(key), "module": module_of(key),
                     "group": group_of(key), "limit": limit, "used": used, "percent": percent,
                     "level": level(percent), "source": source_of(makerspace, key)})
    return rows
