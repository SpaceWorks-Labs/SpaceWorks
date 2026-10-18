"""Typed manual usage, including optional member attribution."""
from decimal import Decimal
from django.db import transaction
from rest_framework.exceptions import ValidationError
from apps.audit import services as audit
from .models import Machine, MachineUsageEntry, MachineServiceRequest, MachineConsumableAdjustment
from .metering import MeteringUnit, metering_unit_for_pool
from .consumable_scope import pool_serves_machine


@transaction.atomic
def log_typed_manual_usage(machine, actor, *, duration_minutes, outcome, percent_complete, reason="", grams=0, quantity=None, metering_unit=None, pool=None, service_request=None, note="", member=None, started_at=None):
    from .service_consumable_pools import _locked_pool, _validate_pool, _grams, _apply
    machine = Machine.objects.select_for_update().select_related("makerspace").get(pk=machine.pk)
    if outcome not in {"success", "failed"}:
        raise ValidationError({"outcome": "Outcome must be success or failed."})
    if not isinstance(duration_minutes, int) or duration_minutes < 0:
        raise ValidationError({"duration_minutes": "Duration must be a non-negative whole number."})
    if not isinstance(percent_complete, int) or not 0 <= percent_complete <= 100:
        raise ValidationError({"percent_complete": "Percent must be between 0 and 100."})
    if outcome == "failed" and not str(reason).strip():
        raise ValidationError({"reason": "A failure reason is required."})
    grams = _grams(grams, "grams")
    quantity = grams if quantity is None else _grams(quantity, "quantity")
    if pool is not None:
        pool = _locked_pool(pool)
        if not pool_serves_machine(pool, machine):
            raise ValidationError({"consumable_pool": "Consumable pool is incompatible with this machine."})
        _validate_pool(machine, pool)
    if service_request is not None:
        service_request = MachineServiceRequest.objects.select_for_update().get(pk=service_request.pk)
        if service_request.makerspace_id != machine.makerspace_id:
            raise ValidationError({"service_request": "Service request must belong to this makerspace."})
    usage_unit = metering_unit or (metering_unit_for_pool(pool.unit) if pool else None) or MeteringUnit.WEIGHT
    if usage_unit not in MeteringUnit.values:
        raise ValidationError({"metering_unit": "Unsupported metering unit."})
    if pool is not None and metering_unit_for_pool(pool.unit) != usage_unit:
        raise ValidationError({"metering_unit": "Consumable pool unit is incompatible with this metering unit."})
    from .usage_attribution import validate_attribution
    member = validate_attribution(machine, member, started_at)
    entry = MachineUsageEntry.objects.create(
        member=member, started_at=started_at,
        machine=machine, hours=(Decimal(duration_minutes) * Decimal(percent_complete) / Decimal("6000")).quantize(Decimal("0.01")),
        source=MachineUsageEntry.Source.TYPED_MANUAL, service_request=service_request, consumable_pool=pool,
        duration_minutes=duration_minutes, outcome=outcome, percent_complete=percent_complete,
        reason=str(reason).strip(), consumed_grams=grams, note=str(note).strip(), logged_by=actor,
        metering_unit=usage_unit, consumed_quantity=quantity,
    )
    if quantity:
        if pool is None:
            raise ValidationError({"consumable_pool": "A consumable pool is required when quantity is recorded."})
        _apply(pool, actor, kind=MachineConsumableAdjustment.Kind.MANUAL, delta=-quantity, usage_entry=entry, service_request=service_request, reason=reason, metering_unit=usage_unit)
    audit.record(
        actor, "machine.typed_usage_logged", makerspace=machine.makerspace, target=entry,
        meta={"machine_id": machine.pk, "usage_entry_id": entry.pk, "duration_minutes": duration_minutes,
              "outcome": outcome, "grams": str(grams), "quantity": str(quantity), "metering_unit": usage_unit},
    )
    return entry

