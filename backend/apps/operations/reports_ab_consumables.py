"""Finalized consumption, with quantities and recorded costs partitioned explicitly."""

from decimal import Decimal

from django.db.models import Q

from apps.machines import role_scope
from apps.machines.models import MachineConsumableAdjustment, MachineConsumablePool, MachineServiceRequest
from apps.machines.models_service_consumables import ServiceRequestConsumption
from apps.machines.models_tracking import ConsumableCostRecord
from apps.makerspaces.platform import module_enabled
from apps.operations.reports_ab_common import bucket, in_range, percent, result, spaces


USAGE_FIELDS = ("period", "source", "material", "measurement_unit", "currency", "consumed_quantity",
                "reserved_quantity", "adjusted_quantity", "cost_total_minor", "cost_unknown_quantity")
POOL_FIELDS = ("pool_id", "material", "measurement_unit", "remaining_quantity", "initial_quantity",
               "low_threshold", "low_count", "depleted_count", "depletion_percent")


def pool_scope(queryset, scope, prefix=""):
    if scope is None or scope is role_scope.EXEMPT:
        return queryset
    return queryset.filter(Q(**{f"{prefix}machine__isnull": True, f"{prefix}machine_type__isnull": True}) |
                           role_scope.scope_q_for(scope,
        machine_id_paths=(f"{prefix}machine_id",),
        type_id_paths=(f"{prefix}machine__machine_type_id", f"{prefix}machine_type_id")))


def request_scope(queryset, scope):
    if scope is None:
        return queryset
    return queryset.filter(role_scope.scope_q_for(scope,
        machine_id_paths=role_scope.SERVICE_REQUEST_MACHINE_PATHS,
        type_id_paths=role_scope.SERVICE_REQUEST_TYPE_PATHS))


def build_consumable_pools(makerspace_id, *, limit=None, date_range=None, actor=None):
    rows = []
    for space in spaces(makerspace_id, "machines"):
        scope = machine_scope(actor, space.pk)
        pools = pool_scope(MachineConsumablePool.objects.filter(makerspace=space, is_active=True), scope)
        for pool in pools.iterator():
            rows.append(dict(makerspace_id=space.pk, pool_id=pool.pk, material=pool.material,
                measurement_unit=pool.unit, remaining_quantity=pool.remaining_grams,
                initial_quantity=pool.initial_grams, low_threshold=pool.low_threshold_grams,
                low_count=int(pool.low_threshold_grams is not None and pool.remaining_grams <= pool.low_threshold_grams),
                depleted_count=int(pool.remaining_grams <= 0),
                depletion_percent=percent(pool.initial_grams - pool.remaining_grams, pool.initial_grams)))
    rows.sort(key=lambda row: (row["remaining_quantity"], row["pool_id"]))
    return result(POOL_FIELDS, rows, makerspace_id, limit)


def consumption_sources(space, scope):
    """Yield (time, kind, id, label, unit, quantity, measure), once per operation."""
    if module_enabled(space, "machine_service"):
        requests = request_scope(MachineServiceRequest.objects.filter(makerspace=space), scope)
        final = requests.filter(run_consumable_pool__isnull=False,
                                status__in=("completed", "collected", "failed")).select_related("run_consumable_pool")
        for request in final.iterator():
            pool = request.run_consumable_pool
            quantity = request.actual_consumed_quantity
            if quantity is None:
                quantity = request.actual_consumed_grams if pool.unit == "grams" else Decimal(0)
            yield (request.failed_at or request.completed_at, "pooled_service", request.pk,
                   pool.material, pool.unit, quantity, "consumed_quantity")
        # Unfinished reservations reflect current held stock, never finalized consumption.
        for request in requests.exclude(status__in=("completed", "collected", "failed", "rejected")).filter(
            run_consumable_pool__isnull=False,
        ).select_related("run_consumable_pool").iterator():
            pool = request.run_consumable_pool
            quantity = request.reserved_quantity
            if quantity is None:
                quantity = request.reserved_grams if pool.unit == "grams" else Decimal(0)
            if quantity:
                yield (request.started_at or request.created_at, "reservation", request.pk,
                       pool.material, pool.unit, quantity, "reserved_quantity")
        consumptions = ServiceRequestConsumption.objects.filter(service_request__in=requests
                                                               ).select_related("product")
        for row in consumptions.iterator():
            yield (row.created_at, "non_pool_consumption", row.pk, row.label or (row.product.name if row.product else "Unlabelled"),
                   row.measurement, row.quantity, "consumed_quantity")
    adjustments = pool_scope(MachineConsumableAdjustment.objects.filter(makerspace=space), scope,
                             "consumable_pool__").select_related("consumable_pool")
    for adjustment in adjustments.iterator():
        if adjustment.kind == "reserve":
            continue  # Outstanding reservation quantities are held on the service request.
        manual = adjustment.kind == "manual" and adjustment.usage_entry_id is not None and adjustment.quantity_delta < 0
        yield (adjustment.created_at, "manual_adjustment" if manual else "adjustment", adjustment.pk,
               adjustment.consumable_pool.material, adjustment.consumable_pool.unit,
               -adjustment.quantity_delta if manual else adjustment.quantity_delta,
               "consumed_quantity" if manual else "adjusted_quantity")


def build_consumable_usage(makerspace_id, *, limit=None, date_range=None, grain="day", actor=None):
    records = []
    for space in spaces(makerspace_id, "machines"):
        scope = machine_scope(actor, space.pk)
        costs = {(row.source_kind, row.source_id): row
                 for row in ConsumableCostRecord.objects.filter(makerspace=space).iterator()}
        groups = {}
        for at, kind, source_id, material, unit, quantity, measure in consumption_sources(space, scope):
            if not in_range(at, date_range):
                continue
            cost = costs.get((kind, source_id)) if measure == "consumed_quantity" else None
            currency = cost.currency if cost else "unknown"
            key = (bucket(at, space, grain), kind, material, unit, currency)
            row = groups.setdefault(key, dict(makerspace_id=space.pk, period=key[0], source=kind, material=material,
                measurement_unit=unit, currency=currency, consumed_quantity=Decimal(0), reserved_quantity=Decimal(0),
                adjusted_quantity=Decimal(0), cost_total_minor=0, cost_unknown_quantity=Decimal(0)))
            row[measure] += quantity
            if cost:
                row["cost_total_minor"] += cost.cost_total_minor
            elif measure == "consumed_quantity":
                row["cost_unknown_quantity"] += quantity
        records.extend(groups.values())
    records.sort(key=lambda row: (row["period"], row["measurement_unit"], row["currency"], -row["consumed_quantity"]))
    return result(USAGE_FIELDS, records, makerspace_id, limit,
        meta={"basis": "Final pooled service quantities, typed manual consume adjustments and non-pool consumption rows; recorded minor-unit costs per currency and measurement unit.",
              "limitations": "Missing cost records remain unknown; unfinished reservations and adjustment deltas are separate measures."})


def machine_scope(actor, space_id):
    if actor is None:
        return None  # Organization/deployment scope is resolved by its upstream boundary.
    from apps.accounts import rbac
    from apps.admin_api.permissions import require_action
    require_action(actor, rbac.Action.MANAGE_MACHINES, space_id)
    return role_scope.manage_scope_for(actor, space_id)
