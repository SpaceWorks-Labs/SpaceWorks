"""Consumables per machine type (decision 341): what jobs estimated and used, by the type's profile.

One row per space, machine type, consumable key and unit in the window: jobs that recorded it,
the summed estimate (the latest estimate per job), the summed actual, how much came from an
adapter, and the actual's value at the price snapshotted when it was recorded (a value of the
material used, not a charge -- charges live in the payment ledger). Counts only, no person.
Rows are narrowed to service requests on machines or types the actor's role scope covers.
"""

from decimal import Decimal

from apps.machines.models_consumable_profiles import ServiceRequestConsumableUsage as Usage

from .reports_machine_common import requests, result, spaces
from .reports_machine_sessions import window

FIELDS = ("machine_type", "key", "name", "unit", "jobs", "estimated_quantity", "actual_quantity",
          "adapter_quantity", "actual_value")
ZERO = Decimal("0")


def build_machine_consumables(makerspace_id, *, limit=None, date_range=None, actor=None, **_kwargs):
    rows = []
    for space, scope in spaces(makerspace_id, ("machines", "machine_service"), actor):
        start, end = window(date_range)
        usage = (Usage.objects.filter(service_request__in=requests(space, scope), created_at__gte=start,
                                      created_at__lte=end)
                 .select_related("definition__machine_type").order_by("created_at", "id"))
        groups, estimates = {}, {}
        for row in usage:
            identity = (row.makerspace_id, row.definition.machine_type_id, row.key, row.unit)
            group = groups.setdefault(identity, {
                "makerspace_id": row.makerspace_id, "machine_type": row.definition.machine_type.name, "key": row.key,
                "name": row.name, "unit": row.unit, "jobs": set(), "estimated_quantity": ZERO,
                "actual_quantity": ZERO, "adapter_quantity": ZERO, "actual_value": ZERO})
            group["jobs"].add(row.service_request_id)
            if row.phase == Usage.Phase.ESTIMATE:
                estimates[(identity, row.service_request_id)] = row.quantity  # the latest estimate wins
                continue
            group["actual_quantity"] += row.quantity
            if row.source == "adapter":
                group["adapter_quantity"] += row.quantity
            if row.unit_price is not None:
                group["actual_value"] += row.quantity * row.unit_price
        for (identity, _job), quantity in estimates.items():
            groups[identity]["estimated_quantity"] += quantity
        for group in groups.values():
            group["jobs"] = len(group["jobs"])
            group["actual_value"] = group["actual_value"].quantize(Decimal("0.01"))
        rows.extend(sorted(groups.values(), key=lambda g: (g["machine_type"], g["key"], g["unit"])))
    return result(FIELDS, rows, makerspace_id, limit)
