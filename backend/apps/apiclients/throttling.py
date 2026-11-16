import hashlib
import uuid
from threading import RLock

from django.core.cache import cache as default_cache, caches
from django.core.cache.backends.db import DatabaseCache
from django.core.cache.backends.locmem import LocMemCache
from django.core.cache.backends.redis import RedisCache
from django.core.exceptions import ImproperlyConfigured
from django.db import connections, router, transaction
from redis.exceptions import RedisError
from rest_framework.throttling import ScopedRateThrottle

_history_lock = RLock()
_ROLLING = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1] - ARGV[2])
local used = redis.call('ZCARD', KEYS[1])
local allowed = 0
if used < tonumber(ARGV[3]) then
    redis.call('ZADD', KEYS[1], ARGV[1], ARGV[4])
    redis.call('PEXPIRE', KEYS[1], math.ceil(ARGV[2] * 1000))
    allowed = 1
end
local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
return {allowed, oldest[2] or ARGV[1]}
"""


def _history_admission(backend, key, now, duration, limit):
    history = backend.get(key, [])
    history = [stamp for stamp in history if stamp > now - duration]
    allowed = len(history) < limit
    if allowed:
        history.insert(0, now)
        backend.set(key, history, duration)
    return allowed, min(history) if history else now


def _admit(backend, key, now, duration, limit):
    if isinstance(backend, RedisCache):
        if getattr(backend, "degraded", False):
            return _admit(backend._fallback, key, now, duration, limit)
        try:
            client = backend._cache.get_client(key, write=True)
            allowed, oldest = client.eval(_ROLLING, 1, backend.make_key(key), now, duration, limit, uuid.uuid4().hex)
            return bool(allowed), float(oldest)
        except RedisError as exc:
            if not hasattr(backend, "_mark_down"):
                raise
            backend._mark_down("rolling_admission", exc)
            return _admit(backend._fallback, key, now, duration, limit)
    if isinstance(backend, DatabaseCache):
        alias = router.db_for_write(backend.cache_model_class)
        digest = hashlib.blake2b(backend.make_key(key).encode(), digest_size=8).digest()
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [int.from_bytes(digest, "big", signed=True)])
            return _history_admission(backend, key, now, duration, limit)
    if isinstance(backend, LocMemCache):
        with _history_lock:
            return _history_admission(backend, key, now, duration, limit)
    raise ImproperlyConfigured("Client throttling requires RedisCache, DatabaseCache or LocMemCache.")


class ClientTierRateThrottle(ScopedRateThrottle):
    """Throttle verified ApiClients by tier, otherwise preserve scoped IP throttles."""

    valid_tiers = {"public", "standard", "trusted"}

    def allow_request(self, request, view):
        api_client = getattr(request, "api_client", None)
        if api_client is None:
            return super().allow_request(request, view)

        self.scope = f"client_{self._tier(api_client)}"
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)
        self._apply_space_limit(api_client)
        return self._consume_slot(request, view)

    def _consume_slot(self, request, view):
        self.now = self.timer()
        if self.num_requests == 0:
            self.oldest = self.now
            return False
        key = f"{self.get_cache_key(request, view)}:rolling"
        backend = caches["default"] if self.cache is default_cache else self.cache
        allowed, self.oldest = _admit(backend, key, self.now, self.duration, self.num_requests)
        return allowed

    def wait(self):
        if hasattr(self, "oldest"):
            return max(0.0, self.duration - (self.now - self.oldest))
        return super().wait()

    def _apply_space_limit(self, api_client):
        """Decision 284: the superadmin's per-space `api_requests_per_minute` may only LOWER the tier rate.

        No override (the default) leaves the tier rate exactly as it was; 0 refuses every request.
        """
        if api_client.makerspace_id is None:
            return
        from apps.managed_hosting.extra_quotas import quota_limit
        cap = quota_limit(api_client.makerspace, "api_requests_per_minute")
        if cap is not None and cap * self.duration < self.num_requests * 60:
            self.num_requests, self.duration = cap, 60

    def get_cache_key(self, request, view):
        api_client = getattr(request, "api_client", None)
        if api_client is None:
            return super().get_cache_key(request, view)

        return self.cache_format % {
            "scope": self.scope,
            "ident": api_client.client_id,
        }

    def _tier(self, api_client):
        tier = (api_client.rate_limit_tier or "").strip() or "standard"
        if tier not in self.valid_tiers:
            return "standard"
        return tier


class MemberPrincipalRateThrottle(ClientTierRateThrottle):
    """Use the authenticated member as the abuse principal, retaining API-client/IP fallbacks."""

    def get_cache_key(self, request, view):
        if getattr(request, "api_client", None) is not None:
            return super().get_cache_key(request, view)
        user = getattr(request, "user", None)
        if getattr(user, "is_authenticated", False) and user.pk:
            return self.cache_format % {"scope": self.scope, "ident": f"member:{user.pk}"}
        return super().get_cache_key(request, view)
