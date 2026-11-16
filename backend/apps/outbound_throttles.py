"""Scoped throttles for staff routes that dial a tenant-configured destination (decision 336(c)/(g), L-C2).

Anthias Test/Sync and the image-adapter provider Test each make the server wait on an outside host, so they are
bounded per account on top of the deployment baseline (``config.throttles``). A view that declares
``throttle_classes`` keeps exactly those, so each list repeats the baseline class. Rates: the scope in
``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`` when set, else the default below; a superadmin
``PlatformThrottleRate`` override is honoured from the cached map, like every other scope.
"""
from django.core.cache import cache as default_cache

from config.throttles import DeploymentUserRateThrottle, FixedWindowRateThrottle


class _PerAccount(FixedWindowRateThrottle):
    default_rate = None

    def get_rate(self):
        from apps.managed_hosting.throttle_rates import CACHE_KEY

        try:
            override = (default_cache.get(CACHE_KEY) or {}).get(self.scope)
        except Exception:  # noqa: BLE001 - a broken cache must never break request handling
            override = None
        return override or self.THROTTLE_RATES.get(self.scope) or self.default_rate

    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False) or getattr(user, "pk", None) is None:
            return None
        return self.cache_format % {"scope": self.scope, "ident": f"user:{user.pk}"}


class AnthiasPlayerThrottle(_PerAccount):
    scope = "anthias_player_call"
    default_rate = "20/min"


class ImageAdapterTestThrottle(_PerAccount):
    scope = "image_adapter_test"
    default_rate = "10/min"


ANTHIAS_PLAYER_THROTTLES = [DeploymentUserRateThrottle, AnthiasPlayerThrottle]
IMAGE_ADAPTER_TEST_THROTTLES = [DeploymentUserRateThrottle, ImageAdapterTestThrottle]
