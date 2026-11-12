"""Draw a recorded actual from the stock a profile row links to (decision 341).

* A consumable pool: through the pool ledger (`service_metering._apply`, kind MANUAL), which
  writes the append-only adjustment, the tracked cost and the low-stock To-Buy alert. The
  pool the job already reserved is skipped: the legacy reconcile at completion debits it.
* An inventory item: through Inventory Availability (`consume_available`), the only owner of
  inventory quantity math.

Physical use already happened, so a shortfall never refuses the record: the pool is drawn to
zero (an item is left untouched) and the shortfall is audited for staff to correct.
"""

import logging
from decimal import Decimal

from apps.audit import services as audit

from .consumable_profiles import POOL_UNITS

logger = logging.getLogger(__name__)


def draw(service_request, actor, definition, quantity):
    if definition.consumable_pool_id and definition.consumable_pool_id != service_request.run_consumable_pool_id:
        return _draw_pool(service_request, actor, definition, quantity)
    if definition.product_id:
        return _draw_item(service_request, actor, definition, quantity)
    return None


def _short(actor, service_request, definition, short):
    audit.record(actor, "machine_service.consumable_stock_short", makerspace=service_request.makerspace,
                 target=service_request, meta={"key": definition.key, "short_by": str(short)})


def _draw_pool(service_request, actor, definition, quantity):
    from .models import MachineConsumableAdjustment, MachineConsumablePool
    from .service_metering import _apply
    pool = MachineConsumablePool.objects.select_for_update(of=("self",)).select_related("makerspace").get(
        pk=definition.consumable_pool_id)
    pool_unit, factor = POOL_UNITS.get(definition.unit, (None, None))
    if pool_unit != pool.unit or not pool.is_active:
        logger.warning("machine_profile_pool_mismatch", extra={"definition_id": definition.pk, "pool_id": pool.pk})
        return None
    wanted = (Decimal(quantity) * factor).quantize(Decimal("0.01"))
    taken = min(wanted, pool.remaining_grams)
    if wanted > taken:
        _short(actor, service_request, definition, wanted - taken)
    if taken <= 0:
        return None
    return _apply(pool, actor, kind=MachineConsumableAdjustment.Kind.MANUAL, delta=-taken,
                  service_request=service_request,
                  reason=f"Machine job {service_request.pk}: {definition.name}")


def _draw_item(service_request, actor, definition, quantity):
    from apps.inventory import availability
    from apps.inventory.availability import InsufficientStock
    from apps.inventory.models import InventoryProduct
    product = InventoryProduct.objects.select_for_update().get(pk=definition.product_id)
    try:
        return availability.consume_available(product, int(quantity),
                                              reason=f"Machine job {service_request.pk}: {definition.name}",
                                              actor=actor)
    except InsufficientStock:
        _short(actor, service_request, definition, quantity)
        return None
