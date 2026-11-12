"""Platform default limits (decision 328a): one value per key, set by the superadmin, applying to every space.

Resolution (identical in all three resolvers: ``limits_core.resource_limit``, ``space_quotas.quota_limit``,
``platform_limits.platform_limit``): space override, then a hosted space's plan, then THIS default, then no limit.
Nothing is stored by default, so nothing is enforced by default, on self-hosts and managed installs alike.

The map is cached for a short time and the cache is cleared on every write. A read failure (database or cache)
never turns a configured default into "unlimited" (decision 335(b)): the last map this process or the shared
cache read successfully is used instead. Only a process that has never read the map, with both the database
and the cache unreadable, answers "no default" -- and that process cannot serve the request it is limiting.
"""
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)
CACHE_KEY = "platform-limit-defaults:v1"
LAST_KNOWN_KEY = "platform-limit-defaults:last-known:v1"
CACHE_TTL = 60
_last_known = None  # this process's last successful read


def _remember(data):
    global _last_known
    _last_known = dict(data)
    try:
        cache.set(LAST_KNOWN_KEY, data, None)  # no expiry: a stale value beats an unlimited one
    except Exception:  # noqa: BLE001 - remembering is best effort; the process copy still holds
        logger.warning("platform_limit_default_last_known_unwritable")


def _fallback():
    if _last_known is not None:
        return dict(_last_known)
    try:
        shared = cache.get(LAST_KNOWN_KEY)
    except Exception:  # noqa: BLE001
        shared = None
    if shared is not None:
        return dict(shared)
    logger.error("platform_limit_defaults_never_read")
    return {}


def all_defaults() -> dict:
    """The stored map. A cache outage falls through to the database; a database failure raises."""
    try:
        cached = cache.get(CACHE_KEY)
    except Exception:  # noqa: BLE001 - the database is the source of truth
        cached = None
    if cached is not None:
        return cached
    from .models import PlatformLimitDefault

    data = dict(PlatformLimitDefault.objects.values_list("key", "value"))
    _remember(data)
    try:
        cache.set(CACHE_KEY, data, CACHE_TTL)
    except Exception:  # noqa: BLE001
        logger.warning("platform_limit_default_cache_unwritable")
    return data


def resilient_defaults() -> dict:
    """``all_defaults()``, or the last map known good when the read fails. Never raises."""
    try:
        return all_defaults()
    except Exception:  # noqa: BLE001 - a limit lookup must never break a request
        logger.warning("platform_limit_default_unreadable_using_last_known")
        return _fallback()


def invalidate():
    try:
        cache.delete(CACHE_KEY)
    except Exception:  # noqa: BLE001 - the short TTL bounds a missed delete
        logger.warning("platform_limit_default_cache_undeletable")


def platform_default(key):
    """The platform default for ``key`` (an int) or None = no default. Never raises (see the module doc)."""
    return resilient_defaults().get(key)


def any_default() -> bool:
    return bool(resilient_defaults())
