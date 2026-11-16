"""Inventory creation races and both QR-box aliases share the last-slot lock."""
import pytest
from django.db import connection
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.boxes.models import Box, QrCode
from apps.inventory.models import InventoryProduct
from tests.limits_0120.concurrency_helpers_cx7 import race_posts
from tests.return_helpers import authenticated_client, make_member, make_space
from tests.shop.test_native_shop_limits_cx7 import native_staff_client

pytestmark = pytest.mark.django_db


def callers(space, surface, settings, monkeypatch):
    if surface == "browser":
        actor = make_member("cx7-inventory-race-manager", space)
        return [authenticated_client(actor), authenticated_client(actor)]
    first, _ = native_staff_client(space, surface, settings, monkeypatch)
    second = APIClient()
    second.credentials(**first._credentials)
    return [first, second]


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("route", ["qr-boxes", "qr-containers"])
def test_box_alias_last_slot_and_next_refusal(surface, route, settings, monkeypatch):
    space = make_space("cx7-box-boundary")
    caller = callers(space, surface, settings, monkeypatch)[0]
    space.resource_limit_overrides = {"boxes": 1}
    space.save(update_fields=["resource_limit_overrides"])
    url = reverse(route)
    maximum = caller.post(url, {"makerspace_id": space.pk, "label": "Last"}, format="json")
    assert maximum.status_code == 201
    refused = caller.post(url, {"makerspace_id": space.pk, "label": "Excess"}, format="json")
    assert refused.status_code == 409
    assert refused.json()["code"] == "boxes_quota_reached"
    assert Box.objects.filter(makerspace=space).count() == 1
    assert QrCode.objects.filter(makerspace=space, target_type="box").count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="qr.box_created").count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("key,route", [("products", "admin-inventory"), ("boxes", "qr-boxes"),
                                       ("boxes", "qr-containers")])
def test_two_inventory_http_creates_at_last_slot_have_one_exact_refusal(key, route, surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("cx7-inventory-api-race")
    pair = callers(space, surface, settings, monkeypatch)
    space.resource_limit_overrides = {key: 1}
    space.save(update_fields=["resource_limit_overrides"])
    if key == "products":
        url = reverse(route, kwargs={"makerspace_id": space.pk})
        bodies = [{"name": name, "total_quantity": 1, "available_quantity": 1} for name in ("A", "B")]
        status, code = 400, "limit_reached"
    else:
        url = reverse(route)
        bodies = [{"makerspace_id": space.pk, "label": name} for name in ("A", "B")]
        status, code = 409, "boxes_quota_reached"
    results = race_posts(pair, url, bodies)
    assert sorted(result[0] for result in results) == sorted([201, status])
    assert [body["code"] for actual, body in results if actual == status] == [code]
    if key == "products":
        assert InventoryProduct.objects.filter(makerspace=space).count() == 1
    else:
        assert Box.objects.filter(makerspace=space).count() == 1
        assert QrCode.objects.filter(makerspace=space, target_type="box").count() == 1
        assert AuditLog.objects.filter(makerspace=space, action="qr.box_created").count() == 1
