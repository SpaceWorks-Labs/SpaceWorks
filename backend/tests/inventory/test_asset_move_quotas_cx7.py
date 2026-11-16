"""QR relocation must reserve destination product and asset capacity atomically."""
import pytest
from django.db import connection, transaction

from apps.audit.models import AuditLog
from apps.boxes.asset_rebind import move_asset_across_makerspaces
from apps.boxes.models import QrCode, QrScanEvent
from apps.inventory.models import InventoryAsset, InventoryProduct
from apps.operations.models import InventoryAdjustment
from tests.limits_0120.creator_races_cx7 import race_creators
from tests.test_qr_asset_move_core import _asset_qr, _move_payload, _move_response, _move_setup
from tests.return_helpers import make_product

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_lending]


def snapshot():
    return {model.__name__: list(model.objects.order_by("pk").values()) for model in (
        InventoryProduct, InventoryAsset, QrCode, QrScanEvent, InventoryAdjustment, AuditLog)}


@pytest.mark.parametrize("key", ["products", "assets"])
def test_qr_move_last_destination_slot_then_refusal_changes_neither_tenant(key, settings):
    settings.MANAGED_PLANS_ENABLED = False
    source, destination, actor, first, asset, qr = _move_setup("cx7-qr-capacity")
    second = make_product(source, name="Other tool", tracking_mode="individual",
                          total_quantity=1, available_quantity=1)
    extra = InventoryAsset.objects.create(makerspace=source, product=second, asset_tag="Other")
    other_qr = _asset_qr(extra, actor)
    destination.resource_limit_overrides = {key: 1}
    destination.save(update_fields=["resource_limit_overrides"])
    maximum = _move_response(actor, qr, _move_payload(asset, destination))
    assert maximum.status_code == 200
    assert InventoryProduct.objects.filter(makerspace=destination).count() == 1
    assert InventoryAsset.objects.filter(makerspace=destination).count() == 1
    before = snapshot()
    refused = _move_response(actor, other_qr, _move_payload(extra, destination))
    assert refused.status_code == 400
    assert refused.json()["code"] == "limit_reached"
    assert key in refused.json()["detail"]
    assert snapshot() == before
    first.refresh_from_db()
    assert (first.total_quantity, first.available_quantity) == (0, 0)
    # Raising only the refused destination quota admits the identical move.
    destination.resource_limit_overrides = {key: 2}
    destination.save(update_fields=["resource_limit_overrides"])
    assert _move_response(actor, other_qr, _move_payload(extra, destination)).status_code == 200
    assert InventoryAsset.objects.filter(makerspace=destination).count() == 2


def test_existing_destination_product_still_requires_an_asset_slot(settings):
    settings.MANAGED_PLANS_ENABLED = False
    _, destination, actor, _, asset, qr = _move_setup("cx7-qr-existing")
    target = make_product(destination, name="Existing", tracking_mode="individual",
                          total_quantity=0, available_quantity=0)
    destination.resource_limit_overrides = {"products": 1, "assets": 0}
    destination.save(update_fields=["resource_limit_overrides"])
    body = _move_payload(asset, destination, destination_product_id=target.pk)
    before = snapshot()
    refused = _move_response(actor, qr, body)
    assert refused.status_code == 400
    assert refused.json()["code"] == "limit_reached"
    assert "assets" in refused.json()["detail"]
    assert snapshot() == before
    destination.resource_limit_overrides["assets"] = 1
    destination.save(update_fields=["resource_limit_overrides"])
    maximum = _move_response(actor, qr, body)
    assert maximum.status_code == 200
    assert InventoryProduct.objects.filter(makerspace=destination).count() == 1
    asset.refresh_from_db()
    assert asset.product_id == target.pk


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("key", ["products", "assets"])
def test_two_qr_moves_to_last_destination_slot_admit_one(key, settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    source, destination, actor, _, asset, qr = _move_setup("cx7-qr-race")
    second = make_product(source, name="Other tool", tracking_mode="individual",
                          total_quantity=1, available_quantity=1)
    extra = InventoryAsset.objects.create(makerspace=source, product=second, asset_tag="Other")
    other_qr = _asset_qr(extra, actor)
    destination.resource_limit_overrides = {key: 1}
    destination.save(update_fields=["resource_limit_overrides"])

    def create(index):
        with transaction.atomic():
            move_asset_across_makerspaces(actor, [qr, other_qr][index], destination.pk, None, "")

    assert race_creators(create) == [(201, "created"), (400, "limit_reached")]
    assert InventoryProduct.objects.filter(makerspace=destination).count() == 1
    assert InventoryAsset.objects.filter(makerspace=destination).count() == 1
    assert InventoryAsset.objects.filter(makerspace=source).count() == 1
    assert QrScanEvent.objects.filter(makerspace=destination, context="reassignment").count() == 1
    assert AuditLog.objects.filter(makerspace=destination, action="inventory.asset_moved_makerspace").count() == 1
