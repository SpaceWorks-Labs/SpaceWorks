"""The consumable cost of shop sales that draw on an inventory consumable (decision 216 item 11).

A variant linked to an inventory consumable (`shop.consumable_link`) sells that item's own
units, so each sale is also consumption of a priced consumable. The identity is the
`ShopStockMovement` the availability module wrote for it (one per order and stock variant,
bundle parts included), so the existing unique (makerspace, source_kind, source_id) key makes
every record exactly-once and a replayed settlement records nothing new.

* `shop_sale` -- written in the sale's own transaction through `machines.consumable_costs`,
  freezing the item's price at sale time. Only with the `shop` module AND
  `inventory.consumables` on; an unpriced item stays cost-unknown. It never blocks a sale.
* `shop_return` -- a restock (a recorded return or an uncollected cancellation) reverses the
  sale's cost for the units that came back, at the SALE's frozen price, never today's. It
  follows the sale record, not the switches: a recorded cost is corrected even if the
  capability went off since. A write-off moves no units back and keeps the cost.
"""

import logging
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit.services import record
from apps.makerspaces.platform import feature_enabled, module_enabled

from .models import ShopStockMovement

logger = logging.getLogger(__name__)
SALE, RETURN = "shop_sale", "shop_return"


def costing_enabled(space):
    return module_enabled(space, "shop") and feature_enabled(space, "inventory.consumables")


def _linked(order, kind):
    return list(ShopStockMovement.objects.filter(
        makerspace_id=order.makerspace_id, order_id=order.pk, kind=kind, variant__linked_product__isnull=False,
        variant__makerspace_id=order.makerspace_id).select_related("variant").order_by("pk"))


def record_sale_costs(order, *, actor):
    """Price every linked sale movement of `order` once. Call right after `sell_shop_stock`."""
    if not costing_enabled(order.makerspace):
        return []
    from apps.inventory.models import InventoryProduct
    from apps.machines.consumable_costs import record_cost

    made = []
    for movement in _linked(order, ShopStockMovement.Kind.SALE):
        product = InventoryProduct.objects.filter(pk=movement.variant.linked_product_id,
                                                  makerspace_id=order.makerspace_id).first()
        if product is None or movement.quantity >= 0:
            continue
        try:
            with transaction.atomic():
                row = record_cost(makerspace=order.makerspace, source_kind=SALE, source_id=movement.pk,
                                  quantity=-movement.quantity, measurement_unit="count", price_source=product,
                                  actor=actor)
        except ValidationError:  # a malformed price must not undo money already received
            logger.warning("shop_sale_cost_unrecorded", extra={"movement_id": movement.pk})
            continue
        if row is not None:
            made.append(row)
    return made


def reverse_return_costs(order, *, actor):
    """Reverse, once each, the sale cost of every linked unit `order` put back on the shelf."""
    from apps.machines.models_tracking import ConsumableCostRecord

    returns = _linked(order, ShopStockMovement.Kind.RETURNED)
    if not returns:
        return []
    sales = {m.variant_id: m.pk for m in _linked(order, ShopStockMovement.Kind.SALE)}
    records = ConsumableCostRecord.objects.filter(makerspace_id=order.makerspace_id, source_kind__in=(SALE, RETURN),
                                                  source_id__in=[*sales.values(), *(m.pk for m in returns)])
    by_key = {(row.source_kind, row.source_id): row for row in records}
    made = []
    for movement in returns:
        sale = by_key.get((SALE, sales.get(movement.variant_id)))
        if sale is None or (RETURN, movement.pk) in by_key or movement.quantity <= 0:
            continue
        prior = [by_key[(RETURN, m.pk)] for m in returns
                 if m.variant_id == movement.variant_id and (RETURN, m.pk) in by_key]
        units = min(Decimal(movement.quantity), sale.quantity - sum(r.quantity for r in prior))
        left = sale.cost_total_minor - sum(r.cost_total_minor for r in prior)
        if units <= 0:
            continue
        total = left if units == sale.quantity - sum(r.quantity for r in prior) else min(left, int(
            (units * sale.unit_price_minor_per_measurement_unit).quantize(Decimal(1), rounding=ROUND_HALF_UP)))
        row, created = ConsumableCostRecord.objects.get_or_create(
            makerspace_id=order.makerspace_id, source_kind=RETURN, source_id=movement.pk,
            defaults={"quantity": units, "measurement_unit": sale.measurement_unit, "currency": sale.currency,
                      "unit_price_minor_per_measurement_unit": sale.unit_price_minor_per_measurement_unit,
                      "cost_total_minor": max(total, 0)})
        if created:
            record(actor, "consumable.cost_recorded", makerspace=order.makerspace, target=row,
                   meta={"source_kind": RETURN, "source_id": movement.pk})
            made.append(row)
        by_key[(RETURN, movement.pk)] = row
    return made
