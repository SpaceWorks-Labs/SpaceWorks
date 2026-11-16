"""The Redis cache backend: shared counters while Redis answers, bounded ones while it does not (decision 339).

Django's own ``RedisCache`` raises on every call while Redis is unreachable. Every DRF route carries a
throttle (decision 336c), and a throttle reads the cache, so before this backend a Redis outage answered
500 to every API request -- sign-in included -- long before anything else noticed.

``ResilientRedisCache`` keeps the shared ``RedisCache`` behaviour and, when a call fails with a Redis
error, answers that call from a per-process ``LocMemCache`` instead and skips Redis for the next
``RETRY_AFTER_SECONDS`` (so a dead Redis costs one connect timeout per process per interval, not one per
call). What that means per use is the rule in ``docs/architecture/redis.md``:

* **Rate limits and lockout counters** keep counting, per process. A limit is then at most
  ``rate x workers`` for the length of the outage: weaker, never unlimited, and sign-in keeps working.
* **Read-through caches** miss and fall back to their database read, as they do on a cold cache.
* **Single-use claims** (signed-request nonces, one-time links, possession proofs) must not degrade to
  per-process: a replay could land on a different worker. They call ``claim_once``, which raises
  ``SharedCacheUnavailable`` instead, and the caller refuses the request (fail closed).

Writes made during an outage stay in the process that made them. A delete that Redis never saw is
bounded by that key's own TTL, which is why every key needs one (see the inventory in the doc).
"""

import logging
import time

from django.core.cache import cache as default_cache
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.core.cache.backends.locmem import LocMemCache
from django.core.cache.backends.redis import RedisCache
from redis.exceptions import RedisError

logger = logging.getLogger("config.redis_cache")

RETRY_AFTER_SECONDS = 5
FALLBACK_MAX_ENTRIES = 10_000
_WRAPPED = ("add", "get", "set", "touch", "delete", "get_many", "has_key", "incr", "set_many",
            "delete_many", "clear")


class SharedCacheUnavailable(RuntimeError):
    """The shared cache could not be reached, so a single-use claim cannot be proven."""


class ResilientRedisCache(RedisCache):
    def __init__(self, server, params):
        super().__init__(server, params)
        fallback_params = {key: params[key] for key in ("TIMEOUT", "KEY_PREFIX", "VERSION") if key in params}
        fallback_params["OPTIONS"] = {"MAX_ENTRIES": FALLBACK_MAX_ENTRIES}
        self._fallback = LocMemCache(f"spaceworks-redis-fallback-{id(self)}", fallback_params)
        self._down_until = 0.0

    @property
    def degraded(self):
        """True while this process is answering from its own fallback instead of Redis."""
        return time.monotonic() < self._down_until

    def _mark_down(self, operation, exc):
        first = not self.degraded
        self._down_until = time.monotonic() + RETRY_AFTER_SECONDS
        if first:
            # One line per outage episode per process, not one per call.
            logger.warning("redis_cache_unavailable", extra={"operation": operation,
                                                             "error_type": type(exc).__name__})

    def _call(self, name, *args, **kwargs):
        if not self.degraded:
            try:
                return getattr(RedisCache, name)(self, *args, **kwargs)
            except RedisError as exc:
                self._mark_down(name, exc)
        return getattr(self._fallback, name)(*args, **kwargs)

    def add_shared(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        """``add`` that never degrades: raises ``SharedCacheUnavailable`` instead of claiming locally."""
        if self.degraded:
            raise SharedCacheUnavailable("redis cache degraded")
        try:
            return RedisCache.add(self, key, value, timeout, version)
        except RedisError as exc:
            self._mark_down("add_shared", exc)
            raise SharedCacheUnavailable("redis cache unreachable") from exc


def _wrap(name):
    def method(self, *args, **kwargs):
        return self._call(name, *args, **kwargs)
    method.__name__ = name
    method.__doc__ = getattr(RedisCache, name).__doc__
    return method


for _name in _WRAPPED:
    setattr(ResilientRedisCache, _name, _wrap(_name))


def claim_once(key, timeout, value=1):
    """Atomically claim ``key`` in the shared cache; ``False`` when it was already claimed.

    On Redis this raises ``SharedCacheUnavailable`` rather than claiming in one process only. The
    database cache (cron mode) and the test cache have no such split, so they use plain ``add``.
    """
    strict = getattr(default_cache, "add_shared", None)
    if strict is None:
        return default_cache.add(key, value, timeout)
    return strict(key, value, timeout)
