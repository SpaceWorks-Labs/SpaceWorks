"""A short per-space cache in front of the public stats builder (#170).

The key carries a fingerprint of every switch the payload depends on (the edition, modules,
features, publication flags and the Settings › Public stats group), so a change to any of them is a
new key at once; saving the settings group also deletes the current key. The TTL only
bounds how stale ACTIVITY counts may be.
"""

import hashlib
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

TTL_SECONDS = 60
_FIELDS = (
    "public_site_enabled", "public_inventory_enabled", "public_stats_enabled", "public_stats_show_holder_names",
    "public_stats_sections", "public_stats_period", "public_stats_headline", "public_stats_tv_mode_enabled",
    "public_stats_tv_refresh_seconds", "timezone", "financial_year_start_month",
)


def _pointer(makerspace_id):
    return f"public-stats:v1:{makerspace_id}"


def _key(makerspace):
    from apps.makerspaces.editions import current_edition

    # The deployment edition hides whole sections, so it is part of the key too.
    parts = [current_edition().key, *(repr(getattr(makerspace, name, None)) for name in _FIELDS)]
    parts += [",".join(sorted(makerspace.enabled_modules or [])), ",".join(sorted(makerspace.enabled_features or []))]
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]
    return f"{_pointer(makerspace.pk)}:{digest}"


def cached(makerspace, build):
    """`build()` once per TTL per configuration; the cache failing never fails the page."""
    key = _key(makerspace)
    try:
        hit = cache.get(key)
    except Exception:  # noqa: BLE001 - a cache outage degrades to an uncached read
        logger.warning("public_stats.cache_unavailable", exc_info=True)
        hit = None
    if hit is not None:
        return hit
    value = build()
    try:
        cache.set(key, value, TTL_SECONDS)
        cache.set(_pointer(makerspace.pk), key, TTL_SECONDS)
    except Exception:  # noqa: BLE001
        logger.warning("public_stats.cache_unavailable", exc_info=True)
    return value


def invalidate(makerspace_id):
    try:
        key = cache.get(_pointer(makerspace_id))
        cache.delete_many([k for k in (key, _pointer(makerspace_id)) if k])
    except Exception:  # noqa: BLE001
        logger.warning("public_stats.cache_unavailable", exc_info=True)
