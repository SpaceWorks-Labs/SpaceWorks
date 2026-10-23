"""One staff list of everything a space uses up (MI-40): item consumables, per-machine
consumables and kernel consumable pools.

Read-only and tenant-filtered first on every branch: each branch starts from the path
makerspace, then narrows through the actor's own scope (inventory view action, machine
role scope, pool scope). A row's ``open_to_buy_id`` is only shown when the actor may see
that procurement stream, so a machine operator never learns about a hidden purchase.
Never public.
"""

from apps.accounts import rbac
from apps.makerspaces.platform import module_enabled

OPEN = ("requested", "approved", "ordered", "received")


def _row(source, pk, name, *, unit, remaining, threshold, machine=None, open_item=None):
    low = threshold is not None and threshold > 0 and remaining <= threshold
    return {"source": source, "id": pk, "name": name, "machine_id": getattr(machine, "pk", None),
            "machine_name": getattr(machine, "name", ""), "unit": unit, "remaining": str(remaining),
            "threshold": None if threshold is None else str(threshold),
            "status": "low" if low else "ok", "open_to_buy_id": open_item}


def _open_items(space, actor, field, ids):
    from apps.separability.registry import runtime_active
    if not ids or not runtime_active("procurement") or not module_enabled(space, "procurement"):
        return {}
    from apps.procurement import access
    from apps.procurement.models import ToBuyItem
    kinds = access.viewable_kinds(actor, space.pk)
    rows = access.scope_items(ToBuyItem.objects.filter(
        makerspace=space, kind__in=kinds, status__in=OPEN, moved_to_inventory_at__isnull=True,
        **{f"{field}__in": ids}), actor, space.pk).values_list(field, "pk")
    return {origin: pk for origin, pk in rows}


def _items(actor, space):
    from apps.inventory.models import InventoryProduct
    if not rbac.can(actor, rbac.Action.VIEW_INVENTORY, space.pk):
        return []
    products = list(rbac.scope_by_action(actor, rbac.Action.VIEW_INVENTORY, InventoryProduct.objects.filter(
        makerspace=space, is_consumable=True, is_archived=False)))
    open_items = _open_items(space, actor, "source_product_id", [p.pk for p in products])
    return [_row("item", p.pk, p.name, unit="count", remaining=p.available_quantity,
                 threshold=p.reorder_point or None, open_item=open_items.get(p.pk)) for p in products]


def _machine_rows(actor, space):
    if not module_enabled(space, "machines"):
        return []
    from apps.machines.access import scope_machines_for_actor
    from apps.machines.models import Machine, MachineConsumable
    machine_ids = scope_machines_for_actor(actor, Machine.objects.filter(
        makerspace=space, is_active=True)).values_list("pk", flat=True)
    rows = list(MachineConsumable.objects.filter(machine_id__in=list(machine_ids)).select_related(
        "machine", "product"))
    open_items = _open_items(space, actor, "source_consumable_id", [row.pk for row in rows])
    result = []
    for row in rows:
        if row.measurement == MachineConsumable.Measurement.COUNT:
            product = row.product
            result.append(_row("machine", row.pk, product.name, unit="count", machine=row.machine,
                               remaining=product.available_quantity, threshold=product.reorder_point or None))
        else:
            result.append(_row("machine", row.pk, row.label, unit="grams", machine=row.machine,
                               remaining=row.remaining, threshold=row.low_threshold,
                               open_item=open_items.get(row.pk)))
    return result


def _pools(actor, space):
    if not module_enabled(space, "machine_service"):
        return []
    from apps.admin_api.views_machine_service_printer import scoped_pools
    from apps.machines.models import MachineConsumablePool
    pools = list(scoped_pools(actor, MachineConsumablePool.objects.filter(
        makerspace=space, is_active=True).select_related("machine")))
    open_items = _open_items(space, actor, "source_pool_id", [pool.pk for pool in pools])
    return [_row("pool", pool.pk, f"{pool.material} {pool.color}".strip(), unit=pool.unit,
                 machine=pool.machine, remaining=pool.remaining_grams, threshold=pool.low_threshold_grams,
                 open_item=open_items.get(pool.pk)) for pool in pools]


def consumable_rows(actor, space, *, status=None):
    """Every visible consumable, low ones first, in a stable (status, name, source, id) order.

    A product used by a COUNT machine consumable shows once as stock (``item``) and
    once per machine (``machine``): stock and per-machine use are both real views.
    """
    rows = _items(actor, space) + _machine_rows(actor, space) + _pools(actor, space)
    if status in ("low", "ok"):
        rows = [row for row in rows if row["status"] == status]
    return sorted(rows, key=lambda row: (row["status"] != "low", row["name"].casefold(), row["source"], row["id"]))
