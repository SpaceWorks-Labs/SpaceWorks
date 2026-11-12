"""Decision 336(c): scoped throttles on the signed adapter routes (per device, tighter on credential routes) and the
camera-watch routes (per account). The deployment baseline still applies alongside each scope."""
import uuid

import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from apps.devices import throttles
from apps.devices.views_adapter import AdapterAccessAuthorizeView, AdapterBindingsView, AdapterSessionStartView
from apps.devices.views_adapter_member import JobOwnerWatchView, ViewerFrameView, ViewerSignalView
from apps.devices.views_adapter_more import AdapterKioskStartView
from config.throttles import DeploymentDeviceRateThrottle, DeploymentUserRateThrottle
from tests.parity_0120.adapter_api.adapter_case import adapter_case, plain_member

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def fresh_counters():
    cache.clear()
    yield
    cache.clear()


def test_every_signed_adapter_route_carries_the_device_scope_and_the_baseline():
    assert AdapterBindingsView.throttle_classes == [DeploymentDeviceRateThrottle, throttles.AdapterDeviceThrottle]
    for view in (AdapterAccessAuthorizeView, AdapterSessionStartView, AdapterKioskStartView):
        assert throttles.AdapterCredentialThrottle in view.throttle_classes
        assert throttles.AdapterDeviceThrottle in view.throttle_classes
    for view in (ViewerSignalView, ViewerFrameView):
        assert view.throttle_classes == [DeploymentUserRateThrottle, throttles.AdapterWatchRelayThrottle]
    assert JobOwnerWatchView.throttle_classes == [DeploymentUserRateThrottle, throttles.AdapterWatchStartThrottle]


def test_an_adapter_over_its_budget_gets_429_and_normal_traffic_passes(monkeypatch):
    case = adapter_case("f3-thr-device")
    cache.clear()
    for _ in range(3):  # normal: a handful of calls at the default rate
        assert case["sim"].get("bindings").status_code == 200
    cache.clear()
    monkeypatch.setattr(throttles.AdapterDeviceThrottle, "rate", "2/min", raising=False)
    assert case["sim"].get("bindings").status_code == 200
    assert case["sim"].get("bindings").status_code == 200
    assert case["sim"].get("bindings").status_code == 429


def test_credential_guessing_is_slowed_per_device(monkeypatch):
    case = adapter_case("f3-thr-credential")
    cache.clear()
    monkeypatch.setattr(throttles.AdapterCredentialThrottle, "rate", "1/min", raising=False)
    body = {"binding_id": case["binding_id"], "credential": {"type": "nfc", "value": "04A1B2C3D4"}}
    first = case["sim"].post("access/authorize", body)
    assert first.status_code == 200 and first.data["allowed"] is False
    assert case["sim"].post("access/authorize", body).status_code == 429
    # Other adapter routes keep their own, wider budget.
    assert case["sim"].get("bindings").status_code == 200


def test_watch_relay_routes_are_throttled_per_account(monkeypatch):
    case = adapter_case("f3-thr-watch")
    viewer, other = plain_member("f3-thr-viewer", case["space"]), plain_member("f3-thr-other", case["space"])
    cache.clear()
    monkeypatch.setattr(throttles.AdapterWatchRelayThrottle, "rate", "1/min", raising=False)
    client = APIClient()
    client.force_authenticate(viewer)
    url = reverse("devices:member-adapter-watch-frame", args=[uuid.uuid4()])
    assert client.get(url).status_code == 404  # normal: no such watch, answered
    assert client.get(url).status_code == 429
    second = APIClient()
    second.force_authenticate(other)
    assert second.get(url).status_code == 404  # another account has its own budget


def test_opening_watches_is_throttled_per_account(monkeypatch):
    case = adapter_case("f3-thr-watch-start")
    viewer = plain_member("f3-thr-starter", case["space"])
    cache.clear()
    monkeypatch.setattr(throttles.AdapterWatchStartThrottle, "rate", "1/min", raising=False)
    client = APIClient()
    client.force_authenticate(viewer)
    url = reverse("devices:member-adapter-watch-start", args=[999999])
    assert client.post(url).status_code != 429
    assert client.post(url).status_code == 429
