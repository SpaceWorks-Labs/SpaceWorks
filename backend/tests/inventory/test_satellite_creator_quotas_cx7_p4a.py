"""Inventory counters beyond products: transfers, kiosk credentials and shelf walks."""
import pytest
from django.db import connection
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.boxes.models import Box, QrCode
from apps.devices.models import ShelfCheck
from apps.inventory.models import InventoryProduct
from apps.makerspaces.models import Station, StationCredential
from apps.operations.models import InventoryAdjustment, StockTransfer, StockTransferLine
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.inventory.transfer_quota_helpers_cx7 import payload, transfer_world
from tests.limits_0120.concurrency_helpers_cx7 import race_posts
from tests.return_helpers import make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_devices]
KEYS = ["stock_transfers_monthly", "kiosk_stations", "shelf_checks_monthly"]


def scenario(key, settings):
    settings.MANAGED_PLANS_ENABLED = False
    settings.EVENT_STATION_PIN_PEPPER = "p4a-independent-station-pin-pepper"
    if key == "stock_transfers_monthly":
        space, _, product, boxes = transfer_world()
        url = reverse("stock-transfers", args=[space.pk])
        model, bodies = StockTransfer, [payload(product, box) for box in boxes[:2]]
    else:
        space = make_space("p4a-inventory-satellite")
        if key == "kiosk_stations":
            space.enabled_features = sorted(set(space.enabled_features) | {"inventory.kiosk"})
            model, url = Station, reverse("admin-kiosk-station-list-create", args=[space.pk])
            bodies = [{"name": name, "kind": kind} for name, kind in [("Desk", "handover"), ("Scanner", "scanner")]]
        else:
            space.enabled_modules = sorted(set(space.enabled_modules) | {"devices", "machines", "machine_service"})
            space.enabled_features = sorted(set(space.enabled_features) | {"machines.integrations"})
            InventoryProduct.objects.create(makerspace=space, name="Tool", storage_location="Shelf A")
            model, url = ShelfCheck, reverse("devices:admin-shelf-checks", args=[space.pk])
            bodies = [{"scope_label": name, "entries": [{"location": "Shelf A", "status": "ok"}]}
                      for name in ["Morning", "Afternoon"]]
    space.resource_limit_overrides = {key: 1}
    space.save(update_fields=["enabled_modules", "enabled_features", "resource_limit_overrides"])
    return space, model, url, bodies


def snapshot():
    return {model.__name__: list(model.objects.order_by("pk").values()) for model in (
        InventoryProduct, Box, QrCode, StockTransfer, StockTransferLine, InventoryAdjustment,
        Station, StationCredential, ShelfCheck, AuditLog)}


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("key", KEYS)
def test_inventory_satellite_max_next_has_no_row_audit_credential_or_stock_write(key, surface, settings, monkeypatch):
    space, model, url, bodies = scenario(key, settings)
    caller = callers(space, surface, settings, monkeypatch)[0]
    maximum = caller.post(url, bodies[0], format="json")
    assert maximum.status_code == 201, maximum.content
    before = snapshot()
    refused = caller.post(url, bodies[1], format="json")
    assert (refused.status_code, refused.json()["code"]) == (409, f"{key}_quota_reached")
    assert snapshot() == before
    assert model.objects.filter(makerspace=space).count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("key", KEYS)
def test_inventory_satellite_creators_race_at_last_slot(key, surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space, model, url, bodies = scenario(key, settings)
    pair = callers(space, surface, settings, monkeypatch)
    results = race_posts(pair, url, bodies)
    assert sorted(status for status, _ in results) == [201, 409]
    assert [body["code"] for status, body in results if status == 409] == [f"{key}_quota_reached"]
    assert model.objects.filter(makerspace=space).count() == 1


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("key,switch,field,code", [
    ("stock_transfers_monthly", "stock_transfers", "enabled_modules", "module_disabled"),
    ("kiosk_stations", "inventory.kiosk", "enabled_features", "feature_disabled"),
    ("shelf_checks_monthly", "machines.integrations", "enabled_features", "not_found"),
    ("shelf_checks_monthly", "devices", "enabled_modules", "not_found"),
    ("shelf_checks_monthly", "machines", "enabled_modules", "not_found"),
    ("shelf_checks_monthly", "machine_service", "enabled_modules", "not_found")])
def test_satellite_switch_dependencies_preserve_rows_and_restore_creator(
        key, switch, field, code, surface, settings, monkeypatch):
    space, model, url, bodies = scenario(key, settings)
    caller = callers(space, surface, settings, monkeypatch)[0]
    original = list(getattr(space, field))
    setattr(space, field, [value for value in original if value != switch])
    space.save(update_fields=[field])
    before = snapshot()
    refused = caller.post(url, bodies[0], format="json")
    assert (refused.status_code, refused.json()["code"]) == (404, code)
    assert snapshot() == before
    setattr(space, field, original)
    space.save(update_fields=[field])
    assert caller.post(url, bodies[0], format="json").status_code == 201
    assert model.objects.filter(makerspace=space).count() == 1
