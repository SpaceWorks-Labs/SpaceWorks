"""Finalized quantities for platform counts, following M1 v3 (one source per debit)."""

from django.db.models.functions import Coalesce
from django.db.models import Q

from apps.machines.models import MachineConsumableAdjustment, MachineServiceRequest, ServiceRequestConsumption
from apps.machines import role_scope
from apps.machines.models_tracking import ConsumableCostRecord
from apps.makerspaces.platform import module_enabled
from apps.operations.reports_common import apply_range


def _sources(space, actor):
    services = role_scope.scoped_service_requests(actor, MachineServiceRequest.objects.filter(makerspace=space), [space.pk])
    if not module_enabled(space, "machine_service"):
        services = services.none()
    scope = role_scope.manage_scope_for(actor, space.pk)
    manual = MachineConsumableAdjustment.objects.filter(makerspace=space, kind="manual", quantity_delta__lt=0,
                                                        service_request__isnull=True, usage_entry__isnull=False)
    manual = manual.filter(role_scope.scope_q_for(scope, machine_id_paths=("usage_entry__machine_id",), type_id_paths=("usage_entry__machine__machine_type_id",)))
    non_pool = ServiceRequestConsumption.objects.filter(service_request__in=services)
    return services, manual, non_pool


def consumption_rows(space, date_range, *, actor):
    services, manual, non_pool = _sources(space, actor)
    requests = services.filter(run_consumable_pool__isnull=False, status__in=("completed", "collected", "failed"))
    requests = requests.annotate(finalized_at=Coalesce("completed_at", "failed_at"))
    for row in apply_range(requests, "finalized_at", date_range).values(
        "finalized_at", "run_consumable_pool_id", "run_consumable_pool__unit", "actual_consumed_quantity", "actual_consumed_grams",
    ).iterator():
        if row["finalized_at"] is not None:
            yield {"at": row["finalized_at"], "entity_kind": "pool", "entity_id": row["run_consumable_pool_id"],
                   "quantity": row["actual_consumed_quantity"] if row["actual_consumed_quantity"] is not None else row["actual_consumed_grams"],
                   "unit": row["run_consumable_pool__unit"]}
    for row in apply_range(manual, "created_at", date_range).values("created_at", "consumable_pool_id", "consumable_pool__unit", "quantity_delta").iterator():
        yield {"at": row["created_at"], "entity_kind": "pool", "entity_id": row["consumable_pool_id"],
               "quantity": -row["quantity_delta"], "unit": row["consumable_pool__unit"]}
    for row in apply_range(non_pool, "created_at", date_range).values("created_at", "product_id", "machine_consumable_id", "measurement", "quantity").iterator():
        yield {"at": row["created_at"], "entity_kind": "product" if row["product_id"] else "machine_consumable",
               "entity_id": row["product_id"] or row["machine_consumable_id"], "quantity": row["quantity"], "unit": row["measurement"]}


def cost_rows(space, date_range, *, actor):
    # Missing cost records never imply zero-priced consumption.
    services, manual, non_pool = _sources(space, actor)
    sources = (Q(source_kind="pooled_service", source_id__in=services.values("pk"))
               | Q(source_kind="manual_adjustment", source_id__in=manual.values("pk"))
               | Q(source_kind="non_pool_consumption", source_id__in=non_pool.values("pk")))
    yield from apply_range(ConsumableCostRecord.objects.filter(makerspace=space).filter(sources), "recorded_at", date_range).values(
        "recorded_at", "source_kind", "cost_total_minor", "currency",
    ).iterator()
    # Shop sales of linked consumables are separate facts; their restocks net them (signed).
    from apps.operations.reports_shop_consumable_costs import shop_cost_rows
    yield from shop_cost_rows(space, actor, date_range)
