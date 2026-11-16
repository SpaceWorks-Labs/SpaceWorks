"""Decision 567: rolling HTTP limits and bounded, cross-connection DB admission."""
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.core.cache import caches
from django.core.management import call_command
from django.db import close_old_connections, connection, connections
from django.test.utils import CaptureQueriesContext, override_settings
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor
from apps.apiclients.throttling import ClientTierRateThrottle

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_auth]
TABLE = "test_wp4_rolling_cache"


class BudgetView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = [ClientTierRateThrottle]

    def get(self, request):
        return Response({"ok": True})


def invoke(principal):
    request = APIRequestFactory().get("/budget")
    request.api_client = SimpleNamespace(client_id=principal, rate_limit_tier="standard", makerspace_id=None)
    return BudgetView.as_view()(request)


@pytest.fixture(params=["locmem", "db"])
def backend(request, transactional_db):
    kind = request.param
    configuration = {"default": {
        "BACKEND": "django.core.cache.backends." + ("db.DatabaseCache" if kind == "db" else "locmem.LocMemCache"),
        "LOCATION": TABLE if kind == "db" else "wp4-rolling-memory",
    }}
    try:
        with override_settings(CACHES=configuration):
            if kind == "db":
                call_command("createcachetable", TABLE, database=connection.alias, verbosity=0)
            caches["default"].clear()
            try:
                yield kind
            finally:
                caches["default"].clear()
    finally:
        # Restore the original cache before outer autouse fixtures clear it.
        if kind == "db":
            with connection.cursor() as cursor:
                cursor.execute('DROP TABLE IF EXISTS "test_wp4_rolling_cache"')


def test_minute_boundary_preserves_original_oldest_admission_and_retry_after(backend, monkeypatch):
    clock = [179.5]
    monkeypatch.setattr(ClientTierRateThrottle, "timer", lambda *_: clock[0])
    monkeypatch.setattr(ClientTierRateThrottle, "get_rate", lambda *_: "1/min")
    principal = uuid4().hex
    assert invoke(principal).status_code == 200
    for instant, wait in [(179.6, "60"), (180.0, "60"), (180.1, "60"), (239.49, "1")]:
        clock[0] = instant
        refused = invoke(principal)
        assert (refused.status_code, refused.data["code"], refused["Retry-After"]) == (429, "throttled", wait)
    clock[0] = 239.5
    assert invoke(principal).status_code == 200
    refused = invoke(principal)
    assert (refused.status_code, refused.data["code"], refused["Retry-After"]) == (429, "throttled", "60")


@pytest.mark.parametrize("rate", [2, 6000])
@pytest.mark.parametrize("backend", ["db"], indirect=True)
def test_database_last_slot_is_atomic_and_refusals_have_constant_statement_bound(backend, rate, monkeypatch):
    assert backend == "db"
    monkeypatch.setattr(ClientTierRateThrottle, "timer", lambda *_: 179.5)
    monkeypatch.setattr(ClientTierRateThrottle, "get_rate", lambda *_: str(rate) + "/min")
    principal = uuid4().hex
    key = "throttle_client_standard_" + principal + ":rolling"
    caches["default"].set(key, [179.0] * (rate - 1), 60)
    gate = Barrier(2, timeout=5)

    def worker():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '3s'")
                cursor.execute("SET statement_timeout = '5s'")
                cursor.execute("SELECT pg_backend_pid()")
                pid = cursor.fetchone()[0]
            gate.wait(timeout=5)
            with CaptureQueriesContext(connection) as queries:
                result = invoke(principal)
            return pid, result, len(queries)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        outcomes = [future.result(timeout=15) for future in futures]
    assert len({pid for pid, _, _ in outcomes}) == 2
    assert sorted(response.status_code for _, response, _ in outcomes) == [200, 429]
    refused = [response for _, response, _ in outcomes if response.status_code == 429]
    assert [(r.data["code"], r["Retry-After"]) for r in refused] == [("throttled", "60")]
    assert all(count <= 12 for _, _, count in outcomes)
    assert len(caches["default"].get(key)) == rate
    for _ in range(3):
        with CaptureQueriesContext(connection) as queries:
            response = invoke(principal)
        assert (response.status_code, response.data["code"], response["Retry-After"]) == (429, "throttled", "60")
        assert len(queries) <= 4
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM "test_wp4_rolling_cache"')
        assert cursor.fetchone()[0] == 1


def test_zero_limit_refuses_without_creating_history(backend, monkeypatch):
    monkeypatch.setattr(ClientTierRateThrottle, "timer", lambda *_: 179.5)
    monkeypatch.setattr(ClientTierRateThrottle, "get_rate", lambda *_: "0/min")
    principal = uuid4().hex
    refused = invoke(principal)
    assert (refused.status_code, refused.data["code"], refused["Retry-After"]) == (429, "throttled", "60")
    assert caches["default"].get("throttle_client_standard_" + principal + ":rolling") is None
