"""R2-07: oldest retained admission is independent of timestamp arrival order."""
from threading import Event, Lock, RLock, local
from uuid import uuid4

import pytest
from django.core.cache import caches
from django.db import close_old_connections, connection, connections

from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor
from apps.apiclients import throttling
from apps.apiclients.throttling import ClientTierRateThrottle
from tests.apiclients.test_atomic_rolling_wp_prodfix4 import backend, invoke

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_auth]


def test_reversed_timestamp_and_lock_order_uses_minimum_and_exact_retry_after(backend, monkeypatch):
    clock = local()
    entered, release = Event(), Event()
    admit = throttling._admit
    principal = uuid4().hex
    monkeypatch.setattr(ClientTierRateThrottle, "timer", lambda *_: clock.now)
    monkeypatch.setattr(ClientTierRateThrottle, "get_rate", lambda *_: "2/min")

    def delayed(cache, key, now, duration, limit):
        if now == 179.5:
            entered.set()
            assert release.wait(timeout=8)
        return admit(cache, key, now, duration, limit)

    monkeypatch.setattr(throttling, "_admit", delayed)

    def earlier():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '3s'")
                cursor.execute("SELECT pg_backend_pid()")
                pid = cursor.fetchone()[0]
            clock.now = 179.5
            return pid, invoke(principal)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        early = pool.submit(earlier)
        try:
            assert entered.wait(timeout=5)
            clock.now = 180.5
            response = invoke(principal)
            assert (response.status_code, response.data) == (200, {"ok": True})
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                main_pid = cursor.fetchone()[0]
        finally:
            release.set()
        early_pid, response = early.result(timeout=8)
    assert early_pid != main_pid
    assert (response.status_code, response.data) == (200, {"ok": True})
    key = "throttle_client_standard_" + principal + ":rolling"
    assert caches["default"].get(key) == [179.5, 180.5]
    clock.now = 180.6
    response = invoke(principal)
    assert (response.status_code, response.data["code"], response["Retry-After"]) == (429, "throttled", "59")
    clock.now = 239.5
    response = invoke(principal)
    assert (response.status_code, response.data) == (200, {"ok": True})


@pytest.mark.parametrize("backend", ["locmem"], indirect=True)
def test_locmem_current_rolling_key_serializes_the_last_slot(backend, monkeypatch):
    assert backend == "locmem"
    principal = uuid4().hex
    key = "throttle_client_standard_" + principal + ":rolling"
    cache = caches["default"]
    cache.set(key, [179.0], 60)
    entered, queued, release = Event(), Event(), Event()
    get = type(cache).get
    state_lock, admission_lock = Lock(), RLock()
    counts = {"locks": 0, "reads": 0}

    class ObservedLock:
        def __enter__(self):
            with state_lock:
                counts["locks"] += 1
                if counts["locks"] == 2:
                    queued.set()
            admission_lock.acquire()

        def __exit__(self, *_):
            admission_lock.release()

    def blocked_get(instance, requested, *args, **kwargs):
        value = get(instance, requested, *args, **kwargs)
        if requested == key:
            with state_lock:
                counts["reads"] += 1
                first = counts["reads"] == 1
            if first:
                entered.set()
                assert release.wait(timeout=8)
        return value

    monkeypatch.setattr(throttling, "_history_lock", ObservedLock())
    monkeypatch.setattr(type(cache), "get", blocked_get)
    monkeypatch.setattr(ClientTierRateThrottle, "timer", lambda *_: 179.5)
    monkeypatch.setattr(ClientTierRateThrottle, "get_rate", lambda *_: "2/min")

    def worker():
        try:
            return invoke(principal)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker)
        try:
            assert entered.wait(timeout=5)
            second = pool.submit(worker)
            assert queued.wait(timeout=5)
            assert counts["reads"] == 1
        finally:
            release.set()
        results = [first.result(timeout=8), second.result(timeout=8)]
    assert sorted(response.status_code for response in results) == [200, 429]
    refused = next(response for response in results if response.status_code == 429)
    assert (refused.data["code"], refused["Retry-After"]) == ("throttled", "60")
    assert cache.get(key) == [179.5, 179.0]
