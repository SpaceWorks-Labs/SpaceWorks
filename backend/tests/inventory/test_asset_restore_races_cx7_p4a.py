"""Restored assets compete with scanners and generators for the same tenant capacity."""
import pytest
from django.db import connection
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.boxes.models import QrCode
from apps.inventory.models import InventoryAsset, InventoryProduct
from tests.inventory.test_alternative_creators_cx7_p4a import race
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.return_helpers import make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_lending]


def world(settings):
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("p4a-restore-assets")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"asset_units", "qr_management", "staff_admin"})
    space.resource_limit_overrides = {"assets": 1}
    space.save(update_fields=["enabled_modules", "resource_limit_overrides"])
    return space


def command(space, kind, index):
    product = InventoryProduct.objects.create(makerspace=space, name=f"Parent {index}",
                                               tracking_mode="individual", is_archived=kind == "restore")
    if kind == "restore":
        InventoryAsset.objects.create(makerspace=space, product=product, asset_tag=f"Unit {index}")
        return "patch", reverse("admin-inventory-detail", args=[product.pk]), {"is_archived": False}, 200
    if kind == "generate":
        return "post", reverse("asset-generate", args=[product.pk]), {"count": 1}, 201
    return "post", reverse("qr-external-assign"), {"makerspace_id": space.pk, "value": f"P4A-ASSET-{index}",
        "create_asset": {"product_id": product.pk, "asset_tag": f"Unit {index}"}}, 201


def snapshot():
    return {model.__name__: list(model.objects.order_by("pk").values())
            for model in (InventoryProduct, InventoryAsset, QrCode, AuditLog)}


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_restore_asset_max_next_retains_archived_parent_and_all_children(surface, settings, monkeypatch):
    space = world(settings)
    caller = callers(space, surface, settings, monkeypatch)[0]
    commands = [command(space, "restore", index) for index in range(2)]
    assert caller.patch(commands[0][1], commands[0][2], format="json").status_code == 200
    before = snapshot()
    refused = caller.patch(commands[1][1], commands[1][2], format="json")
    assert (refused.status_code, refused.json()["code"]) == (400, "limit_reached")
    assert snapshot() == before
    assert InventoryAsset.objects.filter(makerspace=space, product__is_archived=False).count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("kinds", [("restore", "restore"), ("restore", "generate"),
                                   ("restore", "scanner"), ("generate", "scanner")])
def test_mixed_asset_creators_at_last_slot_have_exactly_one_winner(kinds, surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space = world(settings)
    pair = callers(space, surface, settings, monkeypatch)
    commands = [command(space, kind, index) for index, kind in enumerate(kinds)]
    results = race(pair, commands)
    assert sum(status == commands[index][3] for index, (status, _) in enumerate(results)) == 1
    assert [(status, body["code"]) for status, body in results if status == 400] == [(400, "limit_reached")]
    assert InventoryAsset.objects.filter(makerspace=space, product__is_archived=False).count() == 1
