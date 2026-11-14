"""Scanner creation and generated asset units have independent HTTP quota proofs."""
import pytest
from django.db import connection
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.boxes.models import QrCode
from apps.inventory.models import InventoryAsset, InventoryProduct
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.limits_0120.concurrency_helpers_cx7 import race_posts
from tests.return_helpers import make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_lending]


def scenario(kind):
    space = make_space("cx7-scanner-capacity")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"asset_units", "qr_management", "staff_admin"})
    space.resource_limit_overrides = {"products" if kind == "product" else "assets": 1}
    space.save(update_fields=["enabled_modules", "resource_limit_overrides"])
    if kind == "product":
        bodies = [{"makerspace_id": space.pk, "value": f"cx7-label-{index}",
                   "create_product": {"name": f"Tool {index}", "total_quantity": 1, "available_quantity": 1}}
                  for index in range(2)]
        model, url = InventoryProduct, reverse("qr-external-assign")
    else:
        parents = [InventoryProduct.objects.create(makerspace=space, name=f"Parent {index}", tracking_mode="individual")
                   for index in range(2)]
        model = InventoryAsset
        if kind == "asset":
            url = reverse("qr-external-assign")
            bodies = [{"makerspace_id": space.pk, "value": f"cx7-label-{index}",
                       "create_asset": {"product_id": parent.pk, "asset_tag": f"Unit {index}"}}
                      for index, parent in enumerate(parents)]
        else:
            url = reverse("asset-generate", kwargs={"pk": parents[0].pk})
            bodies = [{"count": 1}, {"count": 1}]
    return space, model, url, bodies


def snapshot():
    return {model.__name__: list(model.objects.order_by("pk").values()) for model in (
        InventoryProduct, InventoryAsset, QrCode, AuditLog)}


@pytest.mark.parametrize("kind", ["product", "asset", "generate"])
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_scanner_or_generator_max_and_next_refusal_preserve_all_rows(kind, surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space, model, url, bodies = scenario(kind)
    caller = callers(space, surface, settings, monkeypatch)[0]
    maximum = caller.post(url, bodies[0], format="json")
    assert maximum.status_code == 201
    assert model.objects.filter(makerspace=space).count() == 1
    before = snapshot()
    refused = caller.post(url, bodies[1], format="json")
    assert refused.status_code == 400
    assert refused.json()["code"] == "limit_reached"
    assert snapshot() == before


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", ["product", "asset", "generate"])
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_two_scanner_or_generator_creators_racing_at_last_slot_admit_one(kind, surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space, model, url, bodies = scenario(kind)
    results = race_posts(callers(space, surface, settings, monkeypatch), url, bodies)
    assert sorted(status for status, _ in results) == [201, 400]
    assert [body["code"] for status, body in results if status == 400] == ["limit_reached"]
    assert model.objects.filter(makerspace=space).count() == 1
    assert QrCode.objects.filter(makerspace=space).count() == 1
