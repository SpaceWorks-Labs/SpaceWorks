"""One view over EVERY registry limit key: label, unit, area, effective limit and usage (owner rule 261).

Plan rows (``usage.plan_usage``) and ``makerspaces.usage_snapshot`` used to read only the old numeric
keys. This module gives them the whole registry (``KNOWN_LIMIT_KEYS`` minus the boolean
``custom_domain``) grouped by console area, using the same counters enforcement uses.
"""
from apps.makerspaces.limit_registry import AREA_ORDER, area_of
from apps.makerspaces.limits_core import (
    BOOLEAN_LIMIT_KEYS, EXTRA_QUOTA_LIMIT_KEYS, KNOWN_LIMIT_KEYS, NUMERIC_LIMIT_KEYS,
    PLATFORM_CREDENTIAL_LIMIT_KEYS, RESOURCE_LABELS, SPACE_QUOTA_LIMIT_KEYS, resource_limit,
)

BYTE_KEYS = frozenset({"storage", "upload_bytes", "storage_evidence_bytes", "storage_public_images_bytes",
                       "adapter_media_bytes"})
NEW_KEYS = SPACE_QUOTA_LIMIT_KEYS | PLATFORM_CREDENTIAL_LIMIT_KEYS | EXTRA_QUOTA_LIMIT_KEYS


def registry_keys():
    """Every countable limit key, grouped by console area (area order, then key)."""
    keys = KNOWN_LIMIT_KEYS - BOOLEAN_LIMIT_KEYS
    return sorted(keys, key=lambda key: (AREA_ORDER.index(area_of(key)) if area_of(key) in AREA_ORDER else 99, key))


def label_of(key):
    from .extra_quotas import SPECS
    from .platform_limits import LABELS as PLATFORM_LABELS
    from .space_quotas import LABELS as QUOTA_LABELS
    if key in RESOURCE_LABELS:
        return RESOURCE_LABELS[key]
    if key in SPECS:
        return SPECS[key][1]
    return QUOTA_LABELS.get(key) or PLATFORM_LABELS.get(key, key)


def unit_of(key):
    """``bytes`` or ``count`` (money amounts and per-minute rates are plain numbers here)."""
    return "bytes" if key in BYTE_KEYS else "count"


def effective_limit(makerspace, key):
    """Override > plan > none for any key (the resolvers behind each family all share that order)."""
    if key in NUMERIC_LIMIT_KEYS:
        return resource_limit(makerspace, key)
    if key in SPACE_QUOTA_LIMIT_KEYS:
        from .space_quotas import quota_limit
        return quota_limit(makerspace, key)
    if key in PLATFORM_CREDENTIAL_LIMIT_KEYS:
        from .platform_limits import platform_limit
        return platform_limit(makerspace, key)
    from .space_quotas import quota_limit
    return quota_limit(makerspace, key)


def used_of(makerspace, key):
    """Current usage for a NEW-family key (the numeric keys keep their own counters); None if uncountable."""
    try:
        if key in SPACE_QUOTA_LIMIT_KEYS:
            from .space_quotas import quota_used
            return quota_used(makerspace, key)
        if key in PLATFORM_CREDENTIAL_LIMIT_KEYS:
            from .platform_limits import platform_used
            return platform_used(makerspace, key)
        from .extra_quotas import extra_used
        return extra_used(makerspace, key)
    except Exception:  # a counter of a tombstoned or missing app must not break a usage page
        return None
