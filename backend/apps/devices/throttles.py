"""Scoped throttles for the signed Device Adapter API and the camera-watch routes (decision 336c).

The deployment-wide baseline (``config.throttles``) still counts every request; a view that declares
``throttle_classes`` keeps exactly those, so each list below repeats the baseline class and adds the scope.

* ``AdapterDeviceThrottle`` -- every signed adapter route, per device. An access decision writes two rows and
  takes the tenant lock, so a misbehaving adapter must not be able to hammer it.
* ``AdapterCredentialThrottle`` -- the routes that test a credential (access.authorize, session.start, kiosk start),
  per device: a keypad or reader never needs more than about one attempt a second, and a tight budget slows
  guessing across members (the per-credential and per-space budgets live in ``services_adapter_access``).
* ``AdapterWatchStartThrottle`` / ``AdapterWatchRelayThrottle`` -- opening a camera watch, and its signaling,
  frame and end calls, per account.

Rates: ``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"][scope]`` when the deployment sets one, else the default below;
a superadmin ``PlatformThrottleRate`` override is honoured from the cached map, as for the baseline.
"""
from django.core.cache import cache as default_cache

from config.throttles import DeploymentDeviceRateThrottle, DeploymentUserRateThrottle, FixedWindowRateThrottle


class _ScopedRateThrottle(FixedWindowRateThrottle):
    default_rate = None

    def get_rate(self):
        from apps.managed_hosting.throttle_rates import CACHE_KEY

        try:
            override = (default_cache.get(CACHE_KEY) or {}).get(self.scope)
        except Exception:  # noqa: BLE001 - a broken cache must never break request handling
            override = None
        return override or self.THROTTLE_RATES.get(self.scope) or self.default_rate


class _PerDevice(_ScopedRateThrottle):
    def get_cache_key(self, request, view):
        device_id = getattr(getattr(request, "user", None), "device_id", None)
        if device_id is None:
            return None
        return self.cache_format % {"scope": self.scope, "ident": f"device:{device_id}"}


class _PerAccount(_ScopedRateThrottle):
    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False) or getattr(user, "pk", None) is None:
            return None
        return self.cache_format % {"scope": self.scope, "ident": f"user:{user.pk}"}


class AdapterDeviceThrottle(_PerDevice):
    scope = "device_adapter"
    default_rate = "300/min"


class AdapterCredentialThrottle(_PerDevice):
    scope = "device_adapter_credential"
    default_rate = "60/min"


class AdapterWatchStartThrottle(_PerAccount):
    scope = "adapter_watch_start"
    default_rate = "10/min"


class AdapterWatchRelayThrottle(_PerAccount):
    scope = "adapter_watch_relay"
    default_rate = "300/min"


ADAPTER_THROTTLES = [DeploymentDeviceRateThrottle, AdapterDeviceThrottle]
CREDENTIAL_THROTTLES = [*ADAPTER_THROTTLES, AdapterCredentialThrottle]
WATCH_START_THROTTLES = [DeploymentUserRateThrottle, AdapterWatchStartThrottle]
WATCH_RELAY_THROTTLES = [DeploymentUserRateThrottle, AdapterWatchRelayThrottle]
