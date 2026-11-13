"""Machine-service lines: time + material + per job, each resolved on its own (PX3, A7, A11).

Per component, most specific first: the material pool's override (material only), the
machine's override, the machine type's `MakerspaceMachineTypePricing` row (the release-1
per-type price: its single rate is TIME when the type meters minutes, MATERIAL otherwise,
and its flat fee is the per-job price; a row with charging switched off makes the type
free), then the space default. So time AND material can now be charged together.

Time bills `max(minimum, ceil(minutes / increment) x increment)` minutes at the hourly
rate. A failed job is free by default; the space (and later the per-type, per-fault
choice L12 builds, #142 OQ-8) can charge the material used only, or the full price.
"""

import math
from decimal import Decimal

from apps.payments.models_pricing import PriceOverride, PricingDefault
from apps.payments.pricing.components import Component, component
from apps.payments.pricing.quotes import line
from apps.payments.pricing.rates import Rate

T = PriceOverride.TargetType
FAILED = PricingDefault.FailedJobCharge


def _type_rates(card, machine_type):
    """What the per-type row says for each component, or None for "not set here"."""
    from apps.machines.models import MakerspaceMachineTypePricing

    if machine_type is None:
        return {}
    row = MakerspaceMachineTypePricing.objects.filter(makerspace=card.makerspace, machine_type=machine_type).first()
    if row is None:
        return {}
    if not row.payment_enabled:
        free = Rate(source="type_free")
        return {"time": free, "material": free, "per_job": free}
    minutes = (machine_type.capability_config or {}).get("metering_unit") == "minutes"
    rates = {}
    if row.rate_per_unit > 0:
        default = card.default("time")
        if minutes:
            rates["time"] = Rate(amount=row.rate_per_unit * 60, source="type", increment=default.increment,
                                 minimum=default.minimum)
        else:
            rates["material"] = Rate(amount=row.rate_per_unit, source="type")
    if row.flat_fee > 0:
        rates["per_job"] = Rate(amount=row.flat_fee, source="type")
    return rates


def billed_minutes(minutes, rate):
    minutes = max(int(minutes or 0), 0)
    increment = rate.increment if rate.increment and rate.increment > 1 else 1
    billed = math.ceil(minutes / increment) * increment
    # The minimum is a floor on metered time; a job that recorded no time bills none.
    return max(billed, rate.minimum or 0) if minutes > 0 else 0


def lines(card, *, machine=None, machine_type=None, pool=None, minutes=0, quantity=0,
          outcome="completed", failure_charge=None, consumables=()):
    machine_type = machine_type or (machine.machine_type if machine is not None else None)
    middle = _type_rates(card, machine_type)
    machine_target = ((T.MACHINE, machine.pk),) if machine is not None else ()
    pool_target = ((T.CONSUMABLE_POOL, pool.pk),) if pool is not None else ()
    target = {"type": T.MACHINE, "id": machine.pk, "label": machine.name} if machine is not None else None
    charge = failure_charge or card.failed_job_charge
    if outcome == "failed" and charge == FAILED.NONE:
        return [], ("failed_job_free",)
    # A failed job charged "material only" keeps just the material line (#142 OQ-8 b).
    full = outcome != "failed" or charge == FAILED.FULL
    built = []
    time_rate = card.resolve("time", machine_target, middle=middle.get("time"))
    billed = billed_minutes(minutes, time_rate)
    if full and time_rate.amount > 0 and billed > 0:
        built.append(line(component("machines", "time"), currency=card.currency,
                          quantity=Decimal(billed) / Decimal(60), unit_amount=time_rate.amount,
                          rate_source=time_rate.source, target=target,
                          detail={"minutes": int(minutes or 0), "billed_minutes": billed,
                                  "increment": time_rate.increment, "minimum": time_rate.minimum}))
    material_rate = card.resolve("material", pool_target + machine_target, middle=middle.get("material"))
    if material_rate.amount > 0 and Decimal(quantity or 0) > 0:
        material_target = {"type": T.CONSUMABLE_POOL, "id": pool.pk} if pool is not None else target
        built.append(line(component("machines", "material"), currency=card.currency, quantity=Decimal(quantity),
                          unit_amount=material_rate.amount, rate_source=material_rate.source,
                          target=material_target, detail={"unit": getattr(pool, "unit", "") or "unit"}))
    built += consumable_lines(card, consumables, full=full)
    per_job_rate = card.resolve("per_job", machine_target, middle=middle.get("per_job"))
    if full and per_job_rate.amount > 0:
        built.append(line(component("machines", "per_job"), currency=card.currency, quantity=1,
                          unit_amount=per_job_rate.amount, rate_source=per_job_rate.source, target=target))
    notes = () if full or outcome != "failed" else ("failed_job_material_only",)
    return built, notes


# Decision 341: a profile consumable with its own price per unit. Not in the component registry (no
# space-wide default, no override target, no automatic discount): the price lives on the type's profile.
CONSUMABLE = Component("consumable", "Consumable", "consumable_unit", "machine_service_request", read_only=True)
#: A failed job charged "material used only" keeps these kinds; time and per-job lines go.
MATERIAL_KINDS = frozenset({"material"})


def consumable_lines(card, consumables, *, full=True):
    built = []
    for item in consumables or ():
        if not full and item["kind"] not in MATERIAL_KINDS:
            continue
        component = Component(CONSUMABLE.key, item["name"], CONSUMABLE.unit, CONSUMABLE.subject_type)
        built.append(line(component, currency=card.currency, quantity=item["quantity"],
                          unit_amount=item["unit_price"], rate_source="consumable_profile",
                          target={"type": "machine_type_consumable", "id": item["definition_id"],
                                  "label": item["name"]},
                          detail={"key": item["key"], "unit": item["unit"], "kind": item["kind"]}))
    return built


def service_request_quantity(service_request):
    """Material used by a finished job, as the release-1 charge measured it."""
    if service_request.actual_consumed_quantity is not None:
        return Decimal(service_request.actual_consumed_quantity)
    return Decimal(service_request.actual_consumed_grams or 0)
