"""Real transfer fixtures and durable snapshots for quota rollback assertions."""
from apps.audit.models import AuditLog
from apps.boxes.models import Box
from apps.inventory.models import InventoryProduct
from apps.operations.models import InventoryAdjustment, StockTransfer, StockTransferLine
from tests.return_helpers import make_product, make_space


def transfer_world(cross=False):
    source = make_space("cx7-split-source")
    destination = make_space("cx7-split-destination") if cross else source
    for space in {source, destination}:
        space.enabled_modules = sorted(set(space.enabled_modules) | {"stock_transfers"})
        space.save(update_fields=["enabled_modules"])
    boxes = [Box.objects.create(makerspace=destination, label=f"Destination {n}") for n in range(3)]
    product = make_product(source, name="Counted tools", total_quantity=6, available_quantity=6)
    destination.resource_limit_overrides = {"products": 1 if cross else 2}
    destination.save(update_fields=["resource_limit_overrides"])
    return source, destination, product, boxes


def payload(product, box):
    return {"destination_container_id": box.pk, "destination_makerspace_id": box.makerspace_id,
            "reason": "Quota regression", "lines": [{"product_id": product.pk, "quantity": 1}]}


def snapshot():
    # Include timestamps and every bucket, as well as the transaction's children.
    return {model.__name__: list(model.objects.order_by("pk").values())
            for model in (InventoryProduct, StockTransfer, StockTransferLine, InventoryAdjustment, AuditLog)}
