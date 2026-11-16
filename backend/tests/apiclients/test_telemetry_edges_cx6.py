"""Drain real telemetry payloads through the service; Redis is an external test double."""
import json
from datetime import UTC, datetime, timedelta

import pytest
import redis
from django.core.cache import cache
from django.test import RequestFactory, override_settings
from django.utils import timezone

from apps.apiclients import telemetry
from apps.apiclients.models import ApiClient
from apps.makerspaces.models import Makerspace
from tests.test_apiclient_usage_telemetry import FakeRedis

pytestmark = pytest.mark.django_db
AT = datetime(2026, 11, 14, 10, 30, tzinfo=UTC)


@pytest.fixture
def clients():
    space = Makerspace.objects.create(name="Telemetry", slug="cx6-telemetry")
    other = Makerspace.objects.create(name="Telemetry other", slug="cx6-telemetry-other")
    rows = [ApiClient.issue(label=kind, makerspace=tenant, client_type=kind,
            scopes=["public:catalogue:read"], allowed_origins=["https://usage.test"])[0]
            for kind, tenant in [("server", space), ("browser", space), ("server", other)]]
    return rows


def payload(at=AT, ip="2001:db8::1"):
    return json.dumps({"timestamp": at.isoformat(), "resolved_ip": ip})


def test_browser_observation_cannot_update_a_server_client_or_an_unknown_client(clients):
    server, browser, other = clients
    fake = FakeRedis()
    key = telemetry.bucket_key("browser", AT)
    fake.hashes[key] = {server.client_id: payload(), browser.client_id: payload(), "unknown": payload()}
    assert telemetry.flush_usage_observations(now=AT + timedelta(minutes=1), redis_client=fake) == 1
    server.refresh_from_db()
    browser.refresh_from_db()
    other.refresh_from_db()
    assert (server.last_seen_at, other.last_seen_at) == (None, None)
    assert (browser.last_seen_at, browser.last_seen_ip) == (AT, "2001:db8::1")
    assert fake.hashes == {}


def test_newest_signed_or_browser_observation_wins_independent_of_scan_order(clients):
    _, browser, _ = clients
    fake = FakeRedis()
    for kind, at, ip in [("signed", AT, "192.0.2.1"),
                         ("browser", AT + timedelta(minutes=1), "192.0.2.2"),
                         ("browser", AT - timedelta(minutes=1), "192.0.2.3")]:
        fake.hashes[telemetry.bucket_key(kind, at)] = {browser.client_id: payload(at, ip)}
    assert telemetry.flush_usage_observations(now=AT + timedelta(minutes=2), redis_client=fake) == 1
    browser.refresh_from_db()
    assert (browser.last_seen_at, browser.last_seen_ip) == (AT + timedelta(minutes=1), "192.0.2.2")
    assert fake.hashes == {}


@pytest.mark.parametrize("raw", [b"\xff", "garbage", "[]", "null", "{}",
    '{"timestamp": null}', '{"timestamp": "not-a-date"}', '{"timestamp": []}'])
def test_malformed_observation_is_drained_without_changing_the_client(clients, raw):
    server, _, _ = clients
    fake = FakeRedis()
    fake.hashes[telemetry.bucket_key("signed", AT)] = {server.client_id: raw}
    assert telemetry.flush_usage_observations(now=AT + timedelta(minutes=1), redis_client=fake) == 0
    server.refresh_from_db()
    assert (server.last_seen_at, server.last_seen_ip) == (None, None)
    assert fake.hashes == {}


def test_naive_timestamp_and_invalid_ip_are_normalized_in_the_persisted_row(clients):
    server, _, _ = clients
    fake = FakeRedis()
    fake.hashes[telemetry.bucket_key("signed", AT)] = {
        server.client_id.encode(): json.dumps({"timestamp": "2026-11-14T10:30:00", "resolved_ip": "host.test"}).encode()}
    assert telemetry.flush_usage_observations(now=AT + timedelta(minutes=1), redis_client=fake) == 1
    server.refresh_from_db()
    assert (server.last_seen_at, server.last_seen_ip) == (AT, None)


def test_equal_timestamp_does_not_replace_the_previously_recorded_ip(clients):
    server, _, _ = clients
    ApiClient.objects.filter(pk=server.pk).update(last_seen_at=AT, last_seen_ip="192.0.2.9")
    fake = FakeRedis()
    fake.hashes[telemetry.bucket_key("signed", AT)] = {server.client_id: payload()}
    assert telemetry.flush_usage_observations(now=AT + timedelta(minutes=1), redis_client=fake) == 0
    server.refresh_from_db()
    assert (server.last_seen_at, server.last_seen_ip) == (AT, "192.0.2.9")


@pytest.mark.parametrize("failure", [redis.ResponseError("taken by another flusher"), ConnectionError("offline")])
def test_detach_failure_leaves_bucket_for_retry(clients, failure, caplog):
    server, _, _ = clients

    class UnavailableRedis(FakeRedis):
        def rename(self, key, new_key):
            raise failure

    fake = UnavailableRedis()
    key = telemetry.bucket_key("signed", AT)
    fake.hashes[key] = {server.client_id: payload()}
    assert telemetry.flush_usage_observations(now=AT + timedelta(minutes=1), redis_client=fake) == 0
    assert fake.hashes == {key: {server.client_id: payload()}}
    assert ("api_client_usage_bucket_detach_failed" in caplog.text) is isinstance(failure, ConnectionError)
    server.refresh_from_db()
    assert server.last_seen_at is None


def test_malformed_current_and_future_buckets_are_not_consumed(clients):
    server, _, _ = clients
    fake = FakeRedis()
    keys = ["apiclients:usage:signed:not-a-minute", telemetry.bucket_key("signed", AT),
            telemetry.bucket_key("signed", AT + timedelta(minutes=1))]
    fake.hashes = {key: {server.client_id: payload()} for key in keys}
    assert telemetry.flush_usage_observations(now=AT, redis_client=fake) == 0
    assert set(fake.hashes) == set(keys)


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                                       "LOCATION": "cx6-telemetry-fallback"}})
def test_cache_fallback_limits_writes_and_ignores_inactive_clients(clients, monkeypatch):
    server, browser, other = clients
    cache.clear()
    try:
        monkeypatch.setattr(timezone, "now", lambda: AT)
        request = RequestFactory().get("/", REMOTE_ADDR="192.0.2.40")
        telemetry.record_signed_client_observation(request, server)
        first = cache.get(telemetry._last_key("signed", server.client_id))
        assert json.loads(first) == {"timestamp": AT.isoformat(), "resolved_ip": "192.0.2.40"}
        monkeypatch.setattr(timezone, "now", lambda: AT + timedelta(seconds=30))
        request = RequestFactory().get("/", REMOTE_ADDR="192.0.2.41")
        telemetry.record_signed_client_observation(request, server)
        assert cache.get(telemetry._last_key("signed", server.client_id)) == first
        second_at = AT + timedelta(minutes=1)
        monkeypatch.setattr(timezone, "now", lambda: second_at)
        request = RequestFactory().get("/", REMOTE_ADDR="192.0.2.42")
        telemetry.record_signed_client_observation(request, server)
        assert json.loads(cache.get(telemetry._last_key("signed", server.client_id))) == {
            "timestamp": second_at.isoformat(), "resolved_ip": "192.0.2.42"}
        cache.set(telemetry._last_key("browser", browser.client_id), "not-json")
        cache.set(telemetry._last_key("signed", other.client_id), payload())
        ApiClient.objects.filter(pk=other.pk).update(is_active=False)
        assert telemetry.flush_usage_observations() == 1
        server.refresh_from_db()
        browser.refresh_from_db()
        other.refresh_from_db()
        assert (server.last_seen_at, server.last_seen_ip) == (second_at, "192.0.2.42")
        assert (browser.last_seen_at, other.last_seen_at) == (None, None)
        assert telemetry.flush_usage_observations() == 0
    finally:
        cache.clear()
