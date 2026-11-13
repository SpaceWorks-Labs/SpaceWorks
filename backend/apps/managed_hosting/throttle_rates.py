"""Superadmin-editable DRF throttle rates (#234, addendum 3).

Env/settings values (``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]``) stay the defaults. A row in
``PlatformThrottleRate`` overrides one scope; the scope names never change. ``install()`` wraps
``SimpleRateThrottle.get_rate`` once, so every throttle class (they all derive from it) reads the
effective rate without being edited. The override map is cached and the cache is cleared on every
save/delete, so a change applies at the next request. Any failure falls back to the default.
"""

import re

from django.conf import settings
from django.core.cache import cache

CACHE_KEY = "throttle-rate-overrides:v1"
CACHE_TTL = 300
_PERIOD_SECONDS = {"s": 1, "sec": 1, "m": 60, "min": 60, "h": 3600, "hour": 3600, "d": 86400, "day": 86400}
_RATE = re.compile(r"^(\d{1,6})/(s|sec|m|min|h|hour|d|day)$")
MIN_FACTOR = 10  # an override may be at most 10x stricter ...
MAX_FACTOR = 10  # ... or 10x looser than the deployment default.
ABSOLUTE_MAX_PER_SECOND = 1000


def defaults():
    return {scope: str(rate) for scope, rate in settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}).items()
            if rate}


def per_second(rate):
    match = _RATE.match(str(rate).strip())
    if match is None:
        return None
    return int(match.group(1)) / _PERIOD_SECONDS[match.group(2)]


def bounds(scope):
    """``(min_per_second, max_per_second)`` for a scope, derived from its default."""
    base = per_second(defaults().get(scope, ""))
    if base is None:
        return None
    return base / MIN_FACTOR, min(base * MAX_FACTOR, ABSOLUTE_MAX_PER_SECOND)


def validate(scope, rate):
    """Return the normalised rate or raise ``ValueError`` with a human message."""
    if scope not in defaults():
        raise ValueError("Unknown throttle scope.")
    rate = str(rate or "").strip().lower()
    value = per_second(rate)
    if value is None or value <= 0:
        raise ValueError("Use a rate like 30/min (units: sec, min, hour, day).")
    low, high = bounds(scope)
    if value < low or value > high:
        raise ValueError(f"The rate must stay within 10 times either side of the default ({defaults()[scope]}).")
    return rate


def overrides():
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached
    from .models import PlatformThrottleRate

    data = dict(PlatformThrottleRate.objects.values_list("scope", "rate"))
    cache.set(CACHE_KEY, data, CACHE_TTL)
    return data


def invalidate():
    cache.delete(CACHE_KEY)


def effective_rate(scope):
    try:
        return overrides().get(scope) or defaults().get(scope)
    except Exception:  # noqa: BLE001 - a broken override table must never break request handling
        return defaults().get(scope)


def install():
    from rest_framework.throttling import SimpleRateThrottle

    if getattr(SimpleRateThrottle.get_rate, "_spaceworks_override", False):
        return
    original = SimpleRateThrottle.get_rate

    def get_rate(self):
        scope = getattr(self, "scope", None)
        if scope:
            try:
                override = overrides().get(scope)
            except Exception:  # noqa: BLE001
                override = None
            if override:
                return override
        return original(self)

    get_rate._spaceworks_override = True
    SimpleRateThrottle.get_rate = get_rate
