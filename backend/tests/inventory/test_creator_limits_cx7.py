"""Browser and attested native inventory writes pin the inclusive last slot."""
import pytest
from django.urls import reverse

from apps.inventory.models import InventoryProduct
from tests.return_helpers import authenticated_client, make_member, make_space
from tests.shop.test_native_shop_limits_cx7 import native_staff_client

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("suffix", ["", ".space-works.tech"])
def test_product_last_slot_and_next_refusal_keep_existing_rows(surface, suffix, settings, monkeypatch):
    settings.PLATFORM_DOMAIN_SUFFIX = suffix
    settings.INFRA_HOSTS = {"testserver"}
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("cx7-product-boundary")
    if surface == "browser":
        caller = authenticated_client(make_member("cx7-product-manager", space))
    else:
        caller, _ = native_staff_client(space, surface, settings, monkeypatch, host="testserver")
    caller.defaults["HTTP_HOST"] = "testserver"
    space.resource_limit_overrides = {"products": 1}
    space.save(update_fields=["resource_limit_overrides"])
    url = reverse("admin-inventory", kwargs={"makerspace_id": space.pk})
    body = {"name": "Last product", "total_quantity": 1, "available_quantity": 1}
    maximum = caller.post(url, body, format="json")
    assert maximum.status_code == 201
    refused = caller.post(url, {**body, "name": "Excess product"}, format="json")
    assert refused.status_code == 400
    assert refused.json()["code"] == "limit_reached"
    assert refused.json()["detail"] == refused.json()["limit"]
    assert list(InventoryProduct.objects.filter(makerspace=space).values_list("name", flat=True)) == ["Last product"]
    space.resource_limit_overrides = {"products": 2}
    space.save(update_fields=["resource_limit_overrides"])
    restored = caller.post(url, {**body, "name": "Excess product"}, format="json")
    assert restored.status_code == 201
    assert InventoryProduct.objects.filter(makerspace=space).count() == 2


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_product_name_length_preserves_the_field_error_contract(surface, settings, monkeypatch):
    space = make_space("cx7-product-name")
    if surface == "browser":
        caller = authenticated_client(make_member("cx7-name-manager", space))
    else:
        caller, _ = native_staff_client(space, surface, settings, monkeypatch)
    url = reverse("admin-inventory", kwargs={"makerspace_id": space.pk})
    body = {"name": "x" * 200, "total_quantity": 1, "available_quantity": 1}
    maximum = caller.post(url, body, format="json")
    assert maximum.status_code == 201
    refused = caller.post(url, {**body, "name": "x" * 201}, format="json")
    assert refused.status_code == 400
    assert refused.json() == {"name": ["Ensure this field has no more than 200 characters."]}
    assert InventoryProduct.objects.filter(makerspace=space).count() == 1
