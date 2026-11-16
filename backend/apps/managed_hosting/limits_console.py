"""The superadmin's per-space limit table: effective value, where it comes from, current use (#234).

Order of authority, identical to enforcement (#236 + addendum): an OWN space is unlimited; a
HOSTED space follows override > plan > unlimited. The built-in fair-use values are only shown as
``suggested`` next to an empty field. Reads the same counters ``check_quota`` uses.
"""

from apps.makerspaces.limits_core import (
    CAP_LIMIT_KEYS, NUMERIC_LIMIT_KEYS, RESOURCE_LABELS, resource_limit, suggested_limit,
)
from apps.makerspaces.limits_usage import _COUNTERS

from django.utils.translation import gettext

from apps.makerspaces.limit_modules import group_of, groups_payload, module_of
from apps.makerspaces.limit_registry import AREA_LABELS, area_of

from .enforcement import MONTHLY_KEYS, MONTHLY_LABELS, NOT_SET, _assignment, monthly_used, plan_limit
from .hosting_type import hosting_active, is_hosted, stored_type
from .limit_defaults import platform_default

_UNIT = {"storage": "bytes", "upload_bytes": "bytes"}


def _daily_notifications(makerspace):
    """Today's per-channel notification counters (the keys without a ``_COUNTERS`` entry)."""
    from django.utils import timezone

    from apps.integrations.models import DailyNotificationCounter

    return dict(DailyNotificationCounter.objects.filter(makerspace=makerspace, day=timezone.now().date())
                .values_list("channel", "count"))


def _source(makerspace, key, hosted):
    overrides = makerspace.resource_limit_overrides or {}
    if key in overrides:
        return "override"
    if not hosted:
        from .limit_defaults import platform_default
        return "default" if platform_default(key) is not None else "own"
    if plan_limit(makerspace, key) is not NOT_SET:
        return "plan"
    from .limit_defaults import platform_default
    return "default" if platform_default(key) is not None else "unlimited"


def limit_rows(makerspace, keys=None, *, limited_only=False):
    """Every numeric fair-use key, plus the plan's monthly allowances when a plan is assigned.

    Daily notification channels read today's ``DailyNotificationCounter``; a per-file cap
    (``CAP_LIMIT_KEYS``) has nothing to count and shows ``used: null``. ``keys`` narrows the
    rows (a role sees only its area's); ``limited_only`` drops unlimited rows before counting,
    so a role card never pays for counters it will not show.
    """
    overrides = makerspace.resource_limit_overrides or {}
    hosted = is_hosted(makerspace)
    wanted = (lambda key: True) if keys is None else (lambda key: key in keys)
    daily = None
    rows = []
    for key in sorted(NUMERIC_LIMIT_KEYS):
        if not wanted(key):
            continue
        effective = resource_limit(makerspace, key)
        if limited_only and effective is None:
            continue
        counter = _COUNTERS.get(key)
        if key in CAP_LIMIT_KEYS:
            used = None
        elif counter:
            used = counter(makerspace)
        else:
            daily = _daily_notifications(makerspace) if daily is None else daily
            used = daily.get(key, 0)
        rows.append({
            "key": key, "label": RESOURCE_LABELS.get(key, key), "unit": _UNIT.get(key, "count"), "area": area_of(key),
            "group": group_of(key), "module": module_of(key), "platform_default": platform_default(key),
            "effective": effective, "source": _source(makerspace, key, hosted),
            "override": overrides.get(key), "has_override": key in overrides,
            "used": used, "suggested": suggested_limit(key),
        })
    if _assignment(makerspace) is not None:
        for key in sorted(MONTHLY_KEYS):
            limit = plan_limit(makerspace, key)
            if not wanted(key) or (limited_only and limit in (NOT_SET, None)):
                continue
            rows.append({
                "key": key, "label": MONTHLY_LABELS[key], "unit": "count", "area": area_of(key),
                "group": group_of(key), "module": module_of(key), "platform_default": platform_default(key),
                "effective": None if limit is NOT_SET else limit,
                "source": "own" if not hosted else "unlimited" if limit is NOT_SET else "plan",
                "override": None, "has_override": False, "used": monthly_used(makerspace, key), "suggested": None,
            })
    from .platform_limits import usage_rows
    from .space_quotas import usage_rows as quota_rows
    return {"areas": [{"key": k, "label": gettext(v)} for k, v in AREA_LABELS.items()],
            "groups": groups_payload(),
            "quota_rows": [{**r, "area": area_of(r["key"]), "group": group_of(r["key"]), "module": module_of(r["key"]),
                            "platform_default": platform_default(r["key"])} for r in quota_rows(makerspace)],
            "custom_domain": bool(overrides.get("custom_domain")), "hosting_type": stored_type(makerspace),
            "hosting_active": hosting_active(), "hosted": hosted, "rows": rows,
            "platform_rows": [{**r, "area": area_of(r["key"]), "group": group_of(r["key"]),
                               "module": module_of(r["key"]), "platform_default": platform_default(r["key"])}
                              for r in usage_rows(makerspace)]}


def effective_limits(makerspace, keys=None, *, limited_only=False):
    """Reusable service: every limit of a space with its effective value, source and current usage."""
    return limit_rows(makerspace, keys, limited_only=limited_only)["rows"]
