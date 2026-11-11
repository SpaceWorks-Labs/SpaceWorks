"""To-Buy and consumables grouped by area (decision 241).

Machines: machine type, then machine. Inventory: item category. Rows come only from each
list's own scoped source -- `procurement.access.scope_items` (stream, switch and machine
type narrowing) and `inventory.consumables.consumable_rows` (inventory view action,
machine scope, pool scope) -- so grouping never shows a row the flat list would not.
"""

from decimal import Decimal

from rest_framework.exceptions import NotFound

from apps.operations.area_tree import GroupTree, money_text, none_key

OPEN_TO_BUY = ("requested", "approved", "ordered")


def type_step(type_id, name):
    return ("machine_type", f"machine_type:{type_id}" if type_id else none_key("machine_type"), name or "")


def machine_step(machine_id, name):
    return ("machine", f"machine:{machine_id}" if machine_id else none_key("machine"), name or "")


def category_step(category_id, name):
    return ("category", f"category:{category_id}" if category_id else none_key("category"), name or "")


def area_step(area):
    return ("area", f"area:{area}", area)


def _tobuy_machine(item):
    """The one machine a printing purchase is for, from its durable provenance."""
    if item.resulting_machine_id:
        return item.resulting_machine
    for pool in (item.source_pool, item.resulting_pool):
        if pool is not None and pool.machine_id:
            return pool.machine
    if item.source_consumable_id:
        return item.source_consumable.machine
    return None


def _tobuy_category(item):
    for product in (item.source_product, item.resulting_product):
        if product is not None and product.category_id:
            return product.category
    return None


def tobuy_tree(actor, space, *, areas=None, status="open"):
    from apps.separability.registry import runtime_active
    if not runtime_active("procurement"):
        raise NotFound()
    from apps.makerspaces.folded_capabilities import TOBUY_KEYS, require_any_capability
    from apps.procurement import access
    from apps.procurement.models import ToBuyItem

    require_any_capability(space, TOBUY_KEYS)
    if not access.can_use(actor, space.pk):
        raise NotFound()
    rows = access.scope_items(ToBuyItem.objects.all(), actor, space.pk).select_related(
        "machine_type", "resulting_machine", "source_pool__machine", "resulting_pool__machine",
        "source_consumable__machine", "source_product__category", "resulting_product__category")
    if status == "open":
        rows = rows.filter(status__in=OPEN_TO_BUY)
    elif status != "all":
        rows = rows.filter(status=status)
    tree = GroupTree()
    for item in rows.order_by("name", "pk"):
        area = "machines" if item.kind == ToBuyItem.Kind.PRINTING else "inventory"
        if areas and area not in areas:
            continue
        if area == "machines":
            machine = _tobuy_machine(item)
            path = [area_step(area), type_step(item.machine_type_id, getattr(item.machine_type, "name", "")),
                    machine_step(getattr(machine, "pk", None), getattr(machine, "name", ""))]
        else:
            category = _tobuy_category(item)
            path = [area_step(area), category_step(getattr(category, "pk", None), getattr(category, "name", ""))]
        unit = item.actual_unit_cost if item.actual_unit_cost is not None else item.estimated_unit_cost
        cost = (unit or Decimal("0")) * item.quantity
        tree.add(path, attention=int(item.status == "requested"), money={"": cost}, item={
            "id": item.pk, "label": item.name, "status": item.status, "quantity": item.quantity,
            "amount": money_text(cost), "currency": ""})
    return tree


def _consumable_context(rows):
    """Category per item row; (machine, type) per machine and pool row."""
    from apps.inventory.models import InventoryProduct
    from apps.machines.models import Machine, MachineConsumablePool

    products = {pk: (category, name) for pk, category, name in InventoryProduct.objects.filter(
        pk__in=[row["id"] for row in rows if row["source"] == "item"]).values_list("pk", "category_id", "category__name")}
    machines = {pk: (type_id, name) for pk, type_id, name in Machine.objects.filter(
        pk__in={row["machine_id"] for row in rows if row["machine_id"]}).values_list(
        "pk", "machine_type_id", "machine_type__name")}
    pools = {pk: (type_id, name) for pk, type_id, name in MachineConsumablePool.objects.filter(
        pk__in=[row["id"] for row in rows if row["source"] == "pool"]).values_list(
        "pk", "machine_type_id", "machine_type__name")}
    return products, machines, pools


def consumables_tree(actor, space, *, areas=None, status=None):
    from apps.accounts import rbac
    from apps.inventory.consumables import consumable_rows
    from apps.makerspaces.folded_capabilities import require_capability
    from apps.makerspaces.guards import require_module

    require_module(space, "staff_admin")
    require_capability(space, "inventory.consumables")
    if not (rbac.can(actor, rbac.Action.VIEW_INVENTORY, space.pk)
            or rbac.can(actor, rbac.Action.MANAGE_MACHINES, space.pk)):
        raise NotFound()
    rows = consumable_rows(actor, space, status=status if status in ("low", "ok") else None)
    products, machines, pools = _consumable_context(rows)
    tree = GroupTree()
    for row in rows:
        area = "inventory" if row["source"] == "item" else "machines"
        if areas and area not in areas:
            continue
        if area == "inventory":
            category_id, category_name = products.get(row["id"], (None, ""))
            path = [area_step(area), category_step(category_id, category_name)]
        else:
            type_id, type_name = machines.get(row["machine_id"], (None, ""))
            if row["source"] == "pool" and not row["machine_id"]:
                type_id, type_name = pools.get(row["id"], (None, ""))
            path = [area_step(area), type_step(type_id, type_name), machine_step(row["machine_id"], row["machine_name"])]
        tree.add(path, attention=int(row["status"] == "low"), item={
            "id": row["id"], "label": row["name"], "status": row["status"], "source": row["source"],
            "quantity": row["remaining"], "unit": row["unit"], "threshold": row["threshold"]})
    return tree
