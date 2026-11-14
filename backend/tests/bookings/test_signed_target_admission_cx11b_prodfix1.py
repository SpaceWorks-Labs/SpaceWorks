"""534: authenticate before tenant concealment; every earlier refusal stays generic."""
import hashlib
import hmac
import time
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.apiclients import scope_registry
from apps.apiclients.crypto import encrypt_secret
from apps.inventory import middleware_hmac
from config.redis_cache import SharedCacheUnavailable
from tests.bookings.integration_read_helpers import PREFIX, principal, read_world
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, switch

pytestmark = [pytest.mark.django_db, pytest.mark.area_bookings, pytest.mark.area_inventory]
AUTH_BODY = {"detail": "Invalid client signature."}
HIDDEN_BODY = {"detail": "Not found.", "code": "not_found"}
GATES = [None, "bookings", "bookings.api_read"]


def headers(client, path, *, nonce=None, timestamp=None, secret=None):
    timestamp = str(int(time.time())) if timestamp is None else str(timestamp)
    nonce = uuid4().hex if nonce is None else nonce
    parts = [b"GET", path.encode(), timestamp.encode()]
    if nonce:
        parts.append(nonce.encode())
    signature = hmac.new((secret or client.get_secret()).encode(),
                         b"\n".join([*parts, b""]), hashlib.sha256).hexdigest()
    result = {"HTTP_X_CLIENT_ID": client.client_id, "HTTP_X_TIMESTAMP": timestamp,
              "HTTP_X_SIGNATURE": signature}
    if nonce:
        result["HTTP_X_NONCE"] = nonce
    return result


def paths(w, kind):
    if kind == "booking":
        return [PREFIX + f"bookings/{pk}/" for pk in (w.booking.pk, w.foreign_booking.pk, 999999999)]
    tail = "bookings/" if kind == "reservations" else ""
    return [PREFIX + f"resources/{pk}/{tail}" for pk in (w.resource.pk, w.other.pk, 999999999)]


def exact(response, status, body, *, authenticated=False):
    assert (response.status_code, response.json().get("code")) == (status, body.get("code"))
    assert response.json() == body
    assert getattr(response.wsgi_request, "api_client_signature_verified", False) is authenticated
    assert hasattr(response.wsgi_request, "api_client") is authenticated
    if status == 404:
        assert response["Cache-Control"] == "private, no-store"
        assert response["Referrer-Policy"] == "no-referrer"


@pytest.fixture(autouse=True)
def clean_cache(settings):
    settings.HMAC_MAX_CLOCK_SKEW_SECONDS = 300
    cache.clear()
    yield
    cache.clear()


@pytest.mark.parametrize("kind", ["resource", "reservations", "booking"])
@pytest.mark.parametrize("gate", GATES)
def test_verified_foreign_and_missing_objects_are_identically_hidden(read_world, kind, gate):
    w = read_world
    local, foreign, missing = paths(w, kind)
    control = APIClient().get(local, **headers(w.client, local))
    assert (control.status_code, control.json().get("code")) == (200, None)
    if gate:
        switch(w.tenant, gate)
    with no_domain_writes():
        for path in (foreign, missing):
            exact(APIClient().get(path, **headers(w.client, path)), 404, HIDDEN_BODY)
        if gate:
            exact(APIClient().get(local, **headers(w.client, local)), 404, HIDDEN_BODY, authenticated=True)


FAILURES = ["unsigned", "bad_signature", "nonce_tampered", "path_tampered", "body_tampered",
            "missing_signature", "missing_nonce", "malformed_nonce", "oversized_nonce",
            "past", "future", "bad_timestamp", "unknown_client", "inactive_client", "wrong_origin",
            "expired_previous_secret"]


@pytest.mark.parametrize("failure", FAILURES)
@pytest.mark.parametrize("gate", GATES)
@pytest.mark.parametrize("required", [False, True], ids=["rollout-off", "enforced"])
def test_authentication_failures_never_resolve_or_disclose_a_target(
        read_world, settings, monkeypatch, failure, gate, required):
    w = read_world
    settings.API_CLIENT_AUTH_REQUIRED = required
    if gate:
        switch(w.tenant, gate)
    if failure == "inactive_client":
        w.client.is_active = False
        w.client.save(update_fields=["is_active"])
    if failure == "expired_previous_secret":
        w.client.previous_secret_encrypted = encrypt_secret("expired-secret")
        w.client.previous_secret_valid_until = timezone.now() - timedelta(seconds=1)
        w.client.save(update_fields=["previous_secret_encrypted", "previous_secret_valid_until"])
    resolutions = []
    original = scope_registry.resolve_target

    def observed(*args):
        resolutions.append(args)
        return original(*args)

    monkeypatch.setattr(scope_registry, "resolve_target", observed)
    for path in paths(w, "resource"):
        nonce = uuid4().hex
        valid = headers(w.client, path, nonce=nonce)
        sent = dict(valid)
        body = b""
        if failure == "unsigned":
            sent = {}
        elif failure == "bad_signature":
            sent["HTTP_X_SIGNATURE"] = "0" * 64
        elif failure == "nonce_tampered":
            sent["HTTP_X_NONCE"] = uuid4().hex
        elif failure == "path_tampered":
            sent = headers(w.client, path + "?different=1", nonce=nonce)
        elif failure == "body_tampered":
            body = b"unsigned-body"
        elif failure == "missing_signature":
            sent.pop("HTTP_X_SIGNATURE")
        elif failure == "missing_nonce":
            sent = headers(w.client, path, nonce="")
        elif failure in {"malformed_nonce", "oversized_nonce"}:
            sent = headers(w.client, path, nonce="bad:nonce" if failure == "malformed_nonce" else "x" * 129)
        elif failure in {"past", "future", "bad_timestamp"}:
            stamp = "not-a-number" if failure == "bad_timestamp" else int(time.time()) + (
                -10000 if failure == "past" else 10000)
            sent = headers(w.client, path, nonce=nonce, timestamp=stamp)
        elif failure == "unknown_client":
            sent["HTTP_X_CLIENT_ID"] = "ck_unknown_" + uuid4().hex
        elif failure == "wrong_origin":
            sent["HTTP_ORIGIN"] = "https://untrusted.example.test"
        elif failure == "expired_previous_secret":
            sent = headers(w.client, path, nonce=nonce, secret="expired-secret")
        with no_domain_writes():
            response = APIClient().generic("GET", path, data=body, content_type="application/octet-stream", **sent)
        exact(response, 401, AUTH_BODY)
    assert resolutions == []
    # Refusal must not burn the real client's nonce, even for a concealed target.
    if failure == "inactive_client":
        w.client.is_active = True
        w.client.save(update_fields=["is_active"])
    with no_domain_writes():
        exact(APIClient().get(path, **valid), 404, HIDDEN_BODY)


@pytest.mark.parametrize("target", ["local", "foreign", "missing"])
@pytest.mark.parametrize("first_secret", ["current", "previous"])
def test_replay_is_refused_before_target_resolution_across_rotated_secrets(
        read_world, monkeypatch, target, first_secret):
    w = read_world
    w.client.previous_secret_encrypted = encrypt_secret(w.client.get_secret())
    w.client.previous_secret_valid_until = timezone.now() + timedelta(minutes=5)
    w.client.set_secret("rotated-secret")
    w.client.save(update_fields=["secret_encrypted", "previous_secret_encrypted", "previous_secret_valid_until"])
    path = paths(w, "resource")[["local", "foreign", "missing"].index(target)]
    nonce = uuid4().hex
    secret = "rotated-secret" if first_secret == "current" else "bkh-test-secret"
    with no_domain_writes():
        first = APIClient().get(path, **headers(w.client, path, nonce=nonce, secret=secret))
    if target == "local":
        assert (first.status_code, first.json().get("code"), first.json()["id"]) == (200, None, w.resource.pk)
    else:
        exact(first, 404, HIDDEN_BODY)

    def forbidden_resolution(*args):
        pytest.fail("A replay reached tenant resolution")

    monkeypatch.setattr(scope_registry, "resolve_target", forbidden_resolution)
    with no_domain_writes():
        for secret in ("rotated-secret", "bkh-test-secret"):
            exact(APIClient().get(path, **headers(w.client, path, nonce=nonce, secret=secret)), 401, AUTH_BODY)


@pytest.mark.parametrize("offset,expected", [(-301, 401), (-300, 200), (300, 200), (301, 401)])
def test_clock_skew_boundary_is_unchanged(read_world, monkeypatch, offset, expected):
    fixed = int(time.time())
    monkeypatch.setattr(middleware_hmac, "time", SimpleNamespace(time=lambda: fixed))
    path = paths(read_world, "resource")[0]
    with no_domain_writes():
        response = APIClient().get(path, **headers(read_world.client, path, timestamp=fixed + offset))
    if expected == 401:
        exact(response, 401, AUTH_BODY)
    else:
        assert (response.status_code, response.json().get("code"), response.json()["id"]) == (
            200, None, read_world.resource.pk)


@pytest.mark.parametrize("target", [0, 1, 2], ids=["local", "foreign", "missing"])
def test_replay_guard_outage_remains_retryable_and_never_resolves_target(read_world, monkeypatch, target):
    def unavailable(*args):
        raise SharedCacheUnavailable("test outage")

    def forbidden_resolution(*args):
        pytest.fail("An unproven nonce reached tenant resolution")

    monkeypatch.setattr(middleware_hmac, "claim_nonce", unavailable)
    monkeypatch.setattr(scope_registry, "resolve_target", forbidden_resolution)
    path = paths(read_world, "resource")[target]
    with no_domain_writes():
        response = APIClient().get(path, **headers(read_world.client, path))
    exact(response, 503, {"detail": "Signed requests are briefly unavailable. Retry shortly.",
                          "code": "replay_guard_unavailable"})
    assert response["Retry-After"] == "5"


def test_nonce_cannot_be_moved_into_legacy_body_before_tenant_resolution(read_world, settings, monkeypatch):
    settings.APICLIENT_REQUIRE_NONCE = False
    path = paths(read_world, "resource")[1]
    nonce = uuid4().hex
    sent = headers(read_world.client, path, nonce=nonce)
    sent.pop("HTTP_X_NONCE")

    def forbidden_resolution(*args):
        pytest.fail("An ambiguous nonce reached tenant resolution")

    monkeypatch.setattr(scope_registry, "resolve_target", forbidden_resolution)
    with no_domain_writes():
        response = APIClient().generic("GET", path, data=(nonce + "\n").encode(),
                                       content_type="application/octet-stream", **sent)
    exact(response, 401, AUTH_BODY)


@pytest.mark.parametrize("kind", ["scope", "browser", "global", "peer"])
@pytest.mark.parametrize("gate", GATES)
def test_target_concealment_never_substitutes_for_principal_or_scope_authority(read_world, kind, gate):
    w = read_world
    client = principal(None if kind == "global" else w.tenant,
                       scopes=["public:read"] if kind == "scope" else None,
                       client_type=kind if kind in {"browser", "peer"} else "server")
    if gate:
        switch(w.tenant, gate)
    for path in paths(w, "resource"):
        with no_domain_writes():
            exact(APIClient().get(path, **headers(client, path)), 401, AUTH_BODY)


@pytest.mark.parametrize("suffix", ["unknown/", "bookings/malformed/"])
def test_unregistered_routes_remain_generic_authentication_refusals(read_world, suffix):
    path = PREFIX + suffix
    with no_domain_writes():
        exact(APIClient().get(path, **headers(read_world.client, path)), 401, AUTH_BODY)
