"""P4a: imports, procurement and restores compete with ordinary inventory writers."""
from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor
from threading import Barrier

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection, connections
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.boxes.models import QrCode
from apps.inventory.models import InventoryAsset, InventoryProduct
from apps.operations.models import InventoryAdjustment
from apps.procurement.models import ToBuyItem
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.return_helpers import make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory]
SURFACES = ["browser", "apple", "android"]


def world(settings):
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("p4a-alternative")
    space.enabled_modules = sorted(set(space.enabled_modules) | {
        "bulk_import", "staff_admin", "public_inventory", "asset_units", "qr_management"})
    space.enabled_features = sorted(set(space.enabled_features) | {"inventory.tobuy"})
    space.resource_limit_overrides = {"products": 1}
    space.save(update_fields=["enabled_modules", "enabled_features", "resource_limit_overrides"])
    return space


def state():
    return {model.__name__: list(model.objects.order_by("pk").values()) for model in (
        InventoryProduct, InventoryAsset, InventoryAdjustment, QrCode, ToBuyItem, AuditLog)}


def command(space, kind, index):
    name = f"Tool {index}"
    row = {"name": name, "total_quantity": 1, "available_quantity": 1}
    if kind == "import":
        return "post", reverse("inventory-import-apply", args=[space.pk]), {"rows": [row]}, 200
    if kind == "file_import":
        data = f"name,total_quantity,available_quantity\n{name},1,1\n".encode()
        return "post", reverse("inventory-import-apply", args=[space.pk]), {
            "file": SimpleUploadedFile("inventory.csv", data, content_type="text/csv")}, 200
    if kind == "procurement":
        item = ToBuyItem.objects.create(makerspace=space, kind="hardware", name=name,
                                        quantity=1, status="received")
        return "post", reverse("procurement:to-buy-move-to-inventory", args=[item.pk]), {
            "mode": "create", "name": name, "quantity": 1, "tracking_mode": "quantity",
            "is_public": True, "public_availability_mode": "status_only",
            "show_public_count": False, "public_self_checkout_enabled": False}, 200
    if kind == "restore":
        product = InventoryProduct.objects.create(makerspace=space, name=name, is_archived=True)
        return "patch", reverse("admin-inventory-detail", args=[product.pk]), {"is_archived": False}, 200
    if kind == "scanner":
        return "post", reverse("qr-external-assign"), {"makerspace_id": space.pk,
            "value": f"P4A-{index}", "create_product": row}, 201
    return "post", reverse("admin-inventory", args=[space.pk]), row, 201


def send(caller, cmd):
    method, url, body, _ = cmd
    if "file" in body:
        body["file"].seek(0)
    return getattr(caller, method)(url, body, format="multipart" if "file" in body else "json")


def race(pair, commands):
    barrier = Barrier(2)

    def run(index):
        close_old_connections()
        try:
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
            barrier.wait(timeout=15)
            response = send(pair[index], commands[index])
            return response.status_code, response.json()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, index) for index in range(2)]
        return [future.result(timeout=30) for future in futures]


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("kind", ["import", "file_import", "procurement", "restore"])
def test_alternative_creator_max_next_has_no_domain_or_audit_writes(kind, surface, settings, monkeypatch):
    space = world(settings)
    caller = callers(space, surface, settings, monkeypatch)[0]
    commands = [command(space, kind, index) for index in range(2)]
    assert send(caller, commands[0]).status_code == commands[0][3]
    before = state()
    refused = send(caller, commands[1])
    assert (refused.status_code, refused.json()["code"]) == (400, "limit_reached")
    assert state() == before
    assert InventoryProduct.objects.filter(makerspace=space, is_archived=False).count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("kinds", [
    ("import", "import"), ("procurement", "procurement"), ("restore", "restore"),
    ("import", "ordinary"), ("import", "procurement"), ("import", "restore"),
    ("import", "scanner"), ("procurement", "ordinary"), ("procurement", "restore"),
    ("procurement", "scanner"), ("restore", "ordinary"), ("restore", "scanner"),
    ("file_import", "file_import"), ("file_import", "ordinary"), ("file_import", "procurement"),
    ("file_import", "restore"), ("file_import", "scanner")])
def test_mixed_product_creators_share_one_last_slot(kinds, surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space = world(settings)
    pair = callers(space, surface, settings, monkeypatch)
    commands = [command(space, kind, index) for index, kind in enumerate(kinds)]
    results = race(pair, commands)
    winners = [index for index, (status, _) in enumerate(results) if status == commands[index][3]]
    assert len(winners) == 1
    assert [(status, body["code"]) for status, body in results if status == 400] == [(400, "limit_reached")]
    assert InventoryProduct.objects.filter(makerspace=space, is_archived=False).count() == 1
    assert InventoryAdjustment.objects.count() == int(kinds[winners[0]] == "procurement")


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("kind,key,is_feature", [
    ("import", "bulk_import", False), ("file_import", "bulk_import", False),
    ("procurement", "inventory.tobuy", True),
    ("procurement", "staff_admin", False), ("restore", "staff_admin", False),
    ("restore", "public_inventory", False)])
def test_creator_switch_off_keeps_data_and_on_restores_same_command(
        kind, key, is_feature, surface, settings, monkeypatch):
    space = world(settings)
    caller = callers(space, surface, settings, monkeypatch)[0]
    cmd = command(space, kind, 0)
    field = "enabled_features" if is_feature else "enabled_modules"
    original = list(getattr(space, field))
    setattr(space, field, [value for value in original if value != key])
    space.save(update_fields=[field])
    before = state()
    refused = send(caller, cmd)
    assert (refused.status_code, refused.json()["code"]) == (
        404, "not_found" if kind == "procurement" else
        "capability_disabled" if is_feature else "module_disabled")
    assert state() == before
    setattr(space, field, original)
    space.save(update_fields=[field])
    assert send(caller, cmd).status_code == cmd[3]
    assert InventoryProduct.objects.filter(makerspace=space, is_archived=False).count() == 1


@pytest.mark.parametrize("surface", SURFACES)
def test_import_at_capacity_updates_existing_without_spending_another_slot(surface, settings, monkeypatch):
    space = world(settings)
    caller = callers(space, surface, settings, monkeypatch)[0]
    cmd = command(space, "import", 0)
    assert send(caller, cmd).status_code == 200
    assert send(caller, cmd).status_code == 200
    assert InventoryProduct.objects.filter(makerspace=space).count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="inventory.bulk_imported").count() == 2
