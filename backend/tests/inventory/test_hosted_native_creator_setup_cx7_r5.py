"""Hosted native setup supplies Host before attestation, login and MFA."""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.inventory.models import InventoryProduct
from tests.return_helpers import make_space
from tests.shop.test_native_shop_limits_cx7 import native_staff_client

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory]


@pytest.mark.parametrize("platform", ["apple", "android"])
def test_host_is_present_through_real_native_authentication_and_copied_quota_client(platform, settings, monkeypatch):
    settings.PLATFORM_DOMAIN_SUFFIX = ".space-works.tech"
    settings.INFRA_HOSTS = {"testserver"}
    settings.MANAGED_PLANS_ENABLED = False
    requests = []
    original = APIClient.generic
    def record(caller, method, path, *args, **kwargs):
        response = original(caller, method, path, *args, **kwargs)
        requests.append((path, response.wsgi_request.META.get("HTTP_HOST"), response.status_code))
        return response
    monkeypatch.setattr(APIClient, "generic", record)
    space = make_space("cx7-r5-hosted-native")
    caller, _ = native_staff_client(space, platform, settings, monkeypatch, host="testserver")
    assert requests == [
        ("/api/v1/auth/device/attestation-challenge", "testserver", 200),
        ("/api/v1/auth/device/login", "testserver", 200),
        ("/api/v1/auth/mfa/enroll", "testserver", 200),
        ("/api/v1/auth/mfa/confirm", "testserver", 200),
    ]
    copied = APIClient(**caller.defaults)
    copied.cookies = caller.cookies.copy()
    copied.credentials(**caller._credentials)
    assert copied.defaults["HTTP_HOST"] == "testserver"
    space.resource_limit_overrides = {"products": 1}
    space.save(update_fields=["resource_limit_overrides"])
    url = reverse("admin-inventory", kwargs={"makerspace_id": space.pk})
    body = {"name": "Last hosted product", "total_quantity": 1, "available_quantity": 1}
    assert copied.post(url, body, format="json").status_code == 201
    before = list(InventoryProduct.objects.filter(makerspace=space).values())
    refused = copied.post(url, {**body, "name": "Next hosted product"}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (400, "limit_reached")
    assert list(InventoryProduct.objects.filter(makerspace=space).values()) == before
    space.resource_limit_overrides = {"products": 2}
    space.save(update_fields=["resource_limit_overrides"])
    assert copied.post(url, {**body, "name": "Next hosted product"}, format="json").status_code == 201
    assert InventoryProduct.objects.filter(makerspace=space).count() == 2
    assert requests[-3:] == [(url, "testserver", 201), (url, "testserver", 400), (url, "testserver", 201)]
