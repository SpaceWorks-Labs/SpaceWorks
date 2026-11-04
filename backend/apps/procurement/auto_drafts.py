"""Fail-safe automatic To-Buy drafts for consumables at their reorder point (MI-40).

Two origins, one rule: at most one open item per origin, written by the system (no
actor), audited `procurement.auto_tobuy_created`, and announced to staff with the stock
`to_buy_created` event. A failure here never aborts the stock change that triggered it,
which is why both hooks run after commit and swallow every error.

- An inventory consumable (`InventoryProduct.is_consumable`) whose available quantity
  falls to or below `reorder_point`. Quantity math already happened in the availability
  module; this only reads the committed counts.
- A per-machine GRAMS `MachineConsumable` whose `remaining` falls to `low_threshold`.
  Every machine-origin row is a machines row (`kind=printing`, `machines.tobuy`).
Kernel consumable pools keep their own hook (`machines/low_stock.py`).
"""

import logging

from django.db import transaction

from apps.audit import services as audit
from apps.makerspaces.folded_capabilities import INVENTORY_TOBUY, MACHINES_TOBUY
from apps.procurement.models import ToBuyItem

logger = logging.getLogger(__name__)
OPEN = (ToBuyItem.Status.REQUESTED, ToBuyItem.Status.APPROVED, ToBuyItem.Status.ORDERED,
        ToBuyItem.Status.RECEIVED)


def _procurement_live(makerspace_id, key):
    """The space locked, or None while the origin's To-Buy switch is off (#128 C-9).

    Item origins feed `inventory.tobuy`, machine origins `machines.tobuy`; each switch
    only ever hides its own rows.
    """
    from apps.makerspaces.folded_capabilities import capability_on, require_capability_locked
    from apps.makerspaces.models import Makerspace
    from apps.separability.registry import runtime_active
    if not runtime_active("procurement"):
        return None
    space = Makerspace.objects.get(pk=makerspace_id)
    if not capability_on(space, key):
        return None
    # Lock order matches create_reorder_draft: makerspace first, then the origin row.
    return require_capability_locked(space, key)


def _open(**origin):
    return ToBuyItem.objects.filter(status__in=OPEN, moved_to_inventory_at__isnull=True, **origin).exists()


def _announce(item):
    from apps.machines.notifications_p2_stock import notify
    transaction.on_commit(lambda: notify(item, "to_buy_created"))
    return item


def schedule_product(product_id):
    transaction.on_commit(lambda: draft_for_product(product_id))


def draft_for_product(product_id):
    from apps.inventory.models import InventoryProduct
    try:
        with transaction.atomic():
            makerspace_id = InventoryProduct.objects.values_list("makerspace_id", flat=True).get(pk=product_id)
            space = _procurement_live(makerspace_id, INVENTORY_TOBUY)
            if space is None:
                return None
            product = InventoryProduct.objects.select_for_update().get(pk=product_id)
            point = product.reorder_point
            if (not product.is_consumable or product.is_archived or point <= 0
                    or product.available_quantity > point or _open(source_product=product)):
                return None
            item = ToBuyItem.objects.create(
                makerspace=space, kind=ToBuyItem.Kind.HARDWARE, status=ToBuyItem.Status.REQUESTED,
                name=f"Restock: {product.name}"[:200], quantity=product.reorder_quantity or point,
                vendor_name=product.supplier, source_product=product,
            )
            audit.record(None, "procurement.auto_tobuy_created", makerspace=space, target=item, meta={
                "to_buy_item_id": item.pk, "product_id": product.pk,
                "available": product.available_quantity, "reorder_point": point})
            return _announce(item)
    except Exception:
        logger.exception("Automatic To-Buy failed for product %s", product_id)
        return None


def schedule_consumable(consumable_id):
    transaction.on_commit(lambda: draft_for_consumable(consumable_id))


def draft_for_consumable(consumable_id):
    from apps.machines.models import MachineConsumable
    try:
        with transaction.atomic():
            row = MachineConsumable.objects.select_related("machine__machine_type").get(pk=consumable_id)
            space = _procurement_live(row.machine.makerspace_id, MACHINES_TOBUY)
            if space is None:
                return None
            row = MachineConsumable.objects.select_for_update(of=("self",)).select_related(
                "machine__machine_type").get(pk=consumable_id)
            threshold = row.low_threshold
            if (row.measurement != MachineConsumable.Measurement.GRAMS or threshold is None
                    or threshold <= 0 or row.remaining > threshold or not row.machine.is_active
                    or _open(source_consumable=row)):
                return None
            item = ToBuyItem.objects.create(
                makerspace=space, kind=ToBuyItem.Kind.PRINTING, status=ToBuyItem.Status.REQUESTED,
                name=f"Restock: {row.label} ({row.machine.name})"[:200], quantity=1,
                machine_type_id=row.machine.machine_type_id, source_consumable=row,
            )
            audit.record(None, "procurement.auto_tobuy_created", makerspace=space, target=item, meta={
                "to_buy_item_id": item.pk, "consumable_id": row.pk,
                "remaining": str(row.remaining), "threshold": str(threshold)})
            return _announce(item)
    except Exception:
        logger.exception("Automatic To-Buy failed for machine consumable %s", consumable_id)
        return None
