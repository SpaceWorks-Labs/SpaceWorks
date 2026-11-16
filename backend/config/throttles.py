"""Deployment-wide DRF baseline throttles (decision 336c).

``REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]`` names the three ``Deployment*`` classes, so every
view that does NOT declare its own ``throttle_classes`` (or ``get_throttles``) gets a generous
ceiling. A view with its own throttles keeps exactly those; a view that must never be throttled
(signature-verified provider webhooks, the free-tier cron tick) declares ``throttle_classes = []``.

Each request is counted by exactly one of the three, by who is asking:

* ``DeploymentDeviceRateThrottle`` -- a signed device (``DevicePrincipal``), per device. A space's
  readers and printers often share one NAT address, so keying them on the IP would let one busy
  machine starve the rest.
* ``DeploymentUserRateThrottle`` -- a signed-in account, per account.
* ``DeploymentAnonRateThrottle`` -- everyone else, per verified API client when one signed the
  request, otherwise per client IP (``NUM_PROXIES``-aware, like every other throttle).

They are fixed-window counters (``cache.add`` + ``cache.incr``), not DRF's sliding history list:
a baseline that runs on every request must cost one small cache entry, not a list of up to
``num_requests`` timestamps rewritten each time. The window allows a burst of up to twice the rate
across a boundary, which is fine for a ceiling this generous. The counters live in the shared
``default`` cache, so the "rate limits are global only when their cache is global" invariant
applies unchanged.

Rates come from settings (``THROTTLE_DEPLOYMENT_*``). A superadmin ``PlatformThrottleRate``
override for these scopes is honoured from the cached override map only: the baseline never adds
a database read to the hot path. The map is loaded by the first request to any scoped-throttle
route and on every refresh after a save, so an override applies within moments on a live server.
"""

from django.core.cache import cache as default_cache
from rest_framework.throttling import SimpleRateThrottle

DEVICE_SCOPE = "deployment_device"
USER_SCOPE = "deployment_user"
ANON_SCOPE = "deployment_anon"


class FixedWindowRateThrottle(SimpleRateThrottle):
    """``SimpleRateThrottle`` with a fixed-window counter. Subclasses set ``scope`` and
    ``get_cache_key``; returning ``None`` from ``get_cache_key`` exempts the request."""

    cache = default_cache

    def allow_request(self, request, view):
        if self.rate is None:
            return True
        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True
        self.now = self.timer()
        window = int(self.now // self.duration)
        self.window_ends = (window + 1) * self.duration
        key = f"{self.key}:{window}"
        # incr first: the steady state is one cache round trip (Redis) or a get+set (DatabaseCache).
        try:
            count = self.cache.incr(key)
        except ValueError:  # the first request of this window opens it
            if self.cache.add(key, 1, self.duration + 1):
                return True
            try:  # another worker opened it between our incr and add
                count = self.cache.incr(key)
            except ValueError:
                return True
        return count <= self.num_requests

    def wait(self):
        return max(0.0, self.window_ends - self.now)


class _DeploymentRateThrottle(FixedWindowRateThrottle):
    def get_rate(self):
        from apps.managed_hosting.throttle_rates import CACHE_KEY

        try:
            override = (default_cache.get(CACHE_KEY) or {}).get(self.scope)
        except Exception:  # noqa: BLE001 - a broken cache must never break request handling
            override = None
        # Never raise for a scope a test or an override left out: no rate means no baseline.
        return override or self.THROTTLE_RATES.get(self.scope)


def _device_id(request):
    return getattr(getattr(request, "user", None), "device_id", None)


class DeploymentDeviceRateThrottle(_DeploymentRateThrottle):
    scope = DEVICE_SCOPE

    def get_cache_key(self, request, view):
        device_id = _device_id(request)
        if device_id is None:
            return None
        return self.cache_format % {"scope": self.scope, "ident": f"device:{device_id}"}


class DeploymentUserRateThrottle(_DeploymentRateThrottle):
    scope = USER_SCOPE

    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        if _device_id(request) is not None or not getattr(user, "is_authenticated", False):
            return None
        pk = getattr(user, "pk", None)
        if pk is None:  # a principal that is not an account: counted nowhere rather than crash
            return None
        return self.cache_format % {"scope": self.scope, "ident": f"user:{pk}"}


class DeploymentAnonRateThrottle(_DeploymentRateThrottle):
    scope = ANON_SCOPE

    def get_cache_key(self, request, view):
        if getattr(getattr(request, "user", None), "is_authenticated", False):
            return None
        api_client = getattr(request, "api_client", None)
        ident = f"client:{api_client.client_id}" if api_client is not None else f"ip:{self.get_ident(request)}"
        return self.cache_format % {"scope": self.scope, "ident": ident}

