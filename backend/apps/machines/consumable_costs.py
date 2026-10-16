"""Snapshot prices in minor currency units at consumption finalization, never at reservation."""

from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction

from rest_framework.exceptions import ValidationError

from apps.audit.services import record
from .models_tracking import ConsumableCostRecord

from apps.inventory.cost_basis import UNITS, validate_price


@transaction.atomic
def record_cost(*, makerspace, source_kind, source_id, quantity, measurement_unit, price_source, actor=None):
    if price_source.makerspace_id != makerspace.pk:
        raise ValidationError("Consumable price must belong to this makerspace.")
    existing = ConsumableCostRecord.objects.filter(makerspace=makerspace, source_kind=source_kind, source_id=source_id).first()
    if existing is not None:
        return existing
    price = price_source.unit_cost
    if price is None:
        return None
    currency, cost_unit = price_source.cost_currency, price_source.cost_unit
    validate_price(price, currency, cost_unit, measurement_unit)
    # unit_cost is a MAJOR currency amount per cost_unit. Use the ledger's currency exponent.
    from apps.payments.money import minor_unit_exponent
    minor_factor = Decimal(10) ** minor_unit_exponent(currency)
    normalized = (Decimal(price) * minor_factor * UNITS[measurement_unit][1] / UNITS[cost_unit][1]).quantize(Decimal("0.0000000001"))
    total = int((Decimal(quantity) * normalized).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    if total > 9223372036854775807:
        raise ValidationError({"unit_cost": "The recorded consumption cost exceeds the supported amount."})
    row, created = ConsumableCostRecord.objects.get_or_create(
        makerspace=makerspace, source_kind=source_kind, source_id=source_id,
        defaults={"quantity": quantity, "measurement_unit": measurement_unit,
                  "unit_price_minor_per_measurement_unit": normalized,
                  "cost_total_minor": total, "currency": currency},
    )
    if created:
        record(actor, "consumable.cost_recorded", makerspace=makerspace, target=row,
               meta={"source_kind": source_kind, "source_id": source_id})
    return row


def record_service_cost(request, actor):
    if request.run_consumable_pool_id is None:
        return None
    from .models_service_consumables import MachineConsumablePool
    pool = MachineConsumablePool.objects.select_for_update().get(pk=request.run_consumable_pool_id)
    return record_cost(makerspace=request.makerspace, source_kind="pooled_service", source_id=request.pk,
                       quantity=request.actual_consumed_quantity, measurement_unit=pool.unit,
                       price_source=pool, actor=actor)
