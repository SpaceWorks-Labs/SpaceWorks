"""Typed manual usage logging, split out of service_consumable_pools (file ceiling).

When a ``service_request`` is linked, this joins the shared machine-service lock order
(C1): write fence -> request -> machine -> pool, the same order cancel/start/complete
and the device printer adapter use, and re-validates request/machine compatibility
under those locks. Unlinked usage keeps machine -> pool. Ledger arithmetic is unchanged.
"""

from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.machines.consumable_scope import pool_serves_machine
from apps.machines.metering import MeteringUnit, metering_unit_for_pool
from apps.machines.models import Machine, MachineConsumableAdjustment, MachineServiceRequest, MachineUsageEntry


def _locked_link(service_request, machine):
    from apps.encryption.write_fence import assert_mapped_write_allowed
    makerspace_id = MachineServiceRequest.objects.filter(pk=service_request.pk).values_list("makerspace_id", flat=True).first()
    if makerspace_id is None:
        raise ValidationError({"service_request": "Service request was not found."})
    assert_mapped_write_allowed(makerspace_id)
    request = MachineServiceRequest.objects.select_for_update(no_key=True, of=("self",)).select_related(
        "queue", "bucket").get(pk=service_request.pk)
    locked = Machine.objects.select_for_update(no_key=True, of=("self",)).select_related("makerspace").get(pk=machine.pk)
    if request.makerspace_id != locked.makerspace_id:
        raise ValidationError({"service_request": "Service request must belong to this makerspace."})
    compatible = (
        request.assigned_machine_id == locked.pk
        or (request.assigned_machine_id is None and request.bucket_id and request.bucket.machine_id == locked.pk)
        or (request.assigned_machine_id is None and request.queue_id
            and request.queue.machine_type_id == locked.machine_type_id)
    )
    if not compatible:
        raise ValidationError({"service_request": "Service request is not compatible with this machine."})
    return request, locked


@transaction.atomic
def log_typed_manual_usage(machine, actor, *, duration_minutes, outcome, percent_complete, reason="", grams=0, quantity=None, metering_unit=None, pool=None, service_request=None, note=""):
    from apps.machines.service_consumable_pools import _apply, _grams, _locked_pool, _validate_pool
    if service_request is not None:
        service_request, machine = _locked_link(service_request, machine)
    else:
        machine = Machine.objects.select_for_update(no_key=True, of=("self",)).select_related("makerspace").get(pk=machine.pk)
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
    usage_unit = metering_unit or (metering_unit_for_pool(pool.unit) if pool else None) or MeteringUnit.WEIGHT
    if usage_unit not in MeteringUnit.values:
        raise ValidationError({"metering_unit": "Unsupported metering unit."})
    if pool is not None and metering_unit_for_pool(pool.unit) != usage_unit:
        raise ValidationError({"metering_unit": "Consumable pool unit is incompatible with this metering unit."})
    entry = MachineUsageEntry.objects.create(
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
