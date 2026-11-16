"""Decision 339 (REDIS-AUTH audit): what the application does while Redis is unreachable.

`redis://127.0.0.1:1/0` refuses connections at once, so these run without a Redis server and without
waiting on a timeout. Rules under test (docs/architecture/redis.md):

* the cache degrades to per-process counters instead of failing the request;
* security throttles stay bounded during the outage, never unlimited;
* single-use claims fail closed rather than claim in one process only.
"""

import pytest
from django.core.cache import caches
from django.core.cache.backends.redis import RedisCache
from django.test import override_settings
from redis.exceptions import ConnectionError as RedisConnectionError
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from config import redis_cache
from config.redis_cache import ResilientRedisCache, SharedCacheUnavailable, claim_once

DEAD_URL = "redis://127.0.0.1:1/0"
DEAD_CACHE = {"default": {"BACKEND": "config.redis_cache.ResilientRedisCache", "LOCATION": DEAD_URL,
                          "OPTIONS": {"socket_connect_timeout": 1, "socket_timeout": 1}}}


def dead_cache():
    return ResilientRedisCache(DEAD_URL, {"OPTIONS": {"socket_connect_timeout": 1, "socket_timeout": 1}})


def test_an_unreachable_redis_answers_from_the_process_fallback_instead_of_raising():
    cache = dead_cache()
    assert cache.add("counter", 1, 30) is True
    assert cache.add("counter", 1, 30) is False
    assert cache.incr("counter") == 2
    assert cache.get("counter") == 2
    assert cache.get_many(["counter", "missing"]) == {"counter": 2}
    cache.delete("counter")
    assert cache.get("counter") is None
    assert cache.degraded


def test_incr_of_a_missing_key_still_raises_value_error_like_every_django_cache():
    cache = dead_cache()
    with pytest.raises(ValueError):
        cache.incr("never-set")


def test_a_single_use_claim_refuses_rather_than_claim_in_one_process():
    cache = dead_cache()
    with pytest.raises(SharedCacheUnavailable):
        cache.add_shared("one-use", 1, 30)
    # ... and keeps refusing during the retry window without touching Redis again.
    with pytest.raises(SharedCacheUnavailable):
        cache.add_shared("one-use", 1, 30)


def test_redis_is_skipped_inside_the_retry_window_and_tried_again_after_it(monkeypatch):
    calls = []

    def failing_get(self, *args, **kwargs):
        calls.append(args[0])
        raise RedisConnectionError("down")

    monkeypatch.setattr(RedisCache, "get", failing_get)
    cache = dead_cache()
    assert cache.get("a") is None and cache.get("b") is None
    assert calls == ["a"]  # the second read went straight to the fallback
    monkeypatch.setattr(RedisCache, "get", lambda self, key, default=None, version=None: "from-redis")
    cache._down_until = 0.0  # the window has passed
    assert cache.get("c") == "from-redis"
    assert not cache.degraded


def test_the_outage_is_logged_once_per_episode_not_once_per_call(caplog):
    cache = dead_cache()
    for _ in range(5):
        cache.get("x")
    assert caplog.text.count("redis_cache_unavailable") == 1


def test_claim_once_uses_plain_add_on_caches_without_a_shared_split():
    # LocMem under pytest, DatabaseCache in cron mode: one store, so `add` is already exact.
    caches["default"].delete("claim-once-test")
    assert claim_once("claim-once-test", 30) is True
    assert claim_once("claim-once-test", 30) is False


@override_settings(CACHES=DEAD_CACHE)
def test_claim_once_on_dead_redis_raises():
    with pytest.raises(SharedCacheUnavailable):
        claim_once("dead-claim", 30)


@pytest.mark.django_db
@override_settings(CACHES=DEAD_CACHE, LOGIN_IP_BLOCK_ENABLED=False)
def test_sign_in_keeps_working_and_stays_rate_limited_while_redis_is_down(monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "login", "3/min")
    client = APIClient()

    def attempt():
        return client.post("/api/v1/auth/login", {"username": "nobody", "password": "wrong-pass-1"},
                           format="json", HTTP_ORIGIN="http://localhost:5000", REMOTE_ADDR="198.51.100.7")

    codes = [attempt().status_code for _ in range(4)]
    assert 500 not in codes
    assert codes[:3] == [401, 401, 401]
    assert codes[3] == 429  # bounded per process, not unlimited


@pytest.mark.django_db
def test_a_signed_request_whose_nonce_cannot_be_recorded_is_refused_with_a_retryable_503(monkeypatch):
    from apps.inventory import middleware_hmac
    from tests.test_apiclient_nonce import ORIGIN, PUBLIC, VALID_NONCE, _signed_headers
    from apps.apiclients.models import ApiClient

    def unavailable(client_id, nonce):
        raise SharedCacheUnavailable("down")

    monkeypatch.setattr(middleware_hmac, "claim_nonce", unavailable)
    api_client, secret = ApiClient.issue(label="redis-down client", allowed_origins=[ORIGIN],
                                         client_type="server", scopes=["public:read"])
    with override_settings(API_CLIENT_AUTH_REQUIRED=False, APICLIENT_REQUIRE_NONCE=False,
                           HMAC_MAX_CLOCK_SKEW_SECONDS=300,
                           HMAC_PROTECTED_PATH_PREFIXES=["/api/public/", "/api/v1/public/"]):
        response = APIClient().get(PUBLIC, **_signed_headers(api_client, secret, nonce=VALID_NONCE))
    assert response.status_code == 503
    assert response.json()["code"] == "replay_guard_unavailable"
    assert response["Retry-After"] == "5"


def test_the_nonce_claim_goes_through_the_strict_shared_claim(monkeypatch):
    from apps.inventory import middleware_nonce

    seen = []
    monkeypatch.setattr(middleware_nonce, "claim_once", lambda key, timeout, value=1: seen.append(key) or True)
    assert middleware_nonce.claim_nonce("client", "nonce-1") is True
    assert seen and seen[0].startswith("apiclient-hmac-nonce:")


def test_the_fallback_is_bounded():
    assert redis_cache.FALLBACK_MAX_ENTRIES <= 10_000
    assert dead_cache()._fallback._max_entries == redis_cache.FALLBACK_MAX_ENTRIES
