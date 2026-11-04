"""Price-override targets: which model each is, its owner check, and who may price it (A9).

Per-item prices belong to whoever already edits the item: inventory items to
`edit_inventory`, machines and material pools to `manage_machines` within the actor's
machine scope, rooms to `manage_bookings`. Every check goes through rbac (and the
machine role scope), so a scoped manager can never price another team's item.
"""

from apps.accounts import rbac
from apps.payments.models_pricing import PriceOverride

T = PriceOverride.TargetType

MODELS = {
    T.INVENTORY_PRODUCT: "inventory.InventoryProduct",
    T.MACHINE: "machines.Machine",
    T.CONSUMABLE_POOL: "machines.MachineConsumablePool",
    T.BOOKABLE_SPACE: "bookings.BookableSpace",
}
ACTIONS = {
    T.INVENTORY_PRODUCT: rbac.Action.EDIT_INVENTORY,
    T.MACHINE: rbac.Action.MANAGE_MACHINES,
    T.CONSUMABLE_POOL: rbac.Action.MANAGE_MACHINES,
    T.BOOKABLE_SPACE: rbac.Action.MANAGE_BOOKINGS,
}
DOMAINS = {
    T.INVENTORY_PRODUCT: "loans",
    T.MACHINE: "machines",
    T.CONSUMABLE_POOL: "machines",
    T.BOOKABLE_SPACE: "bookings",
}


def model_for(target_type):
    from django.apps import apps

    label = MODELS.get(target_type)
    return apps.get_model(label) if label else None


def load(target_type, target_id, makerspace_id):
    model = model_for(target_type)
    if model is None:
        return None
    return model.objects.filter(pk=target_id, makerspace_id=makerspace_id).first()


def can_price(actor, target_type, target):
    """Whether `actor` may change prices on this item."""
    action = ACTIONS.get(target_type)
    if action is None or target is None or not rbac.can(actor, action, target.makerspace_id):
        return False
    if target_type == T.MACHINE:
        from apps.machines.role_scope import covers_machine
        return covers_machine(actor, target)
    if target_type == T.CONSUMABLE_POOL:
        return _covers_pool(actor, target)
    if target_type == T.BOOKABLE_SPACE:
        from apps.bookings.booking_authority import can_manage_grants
        return can_manage_grants(actor, target)
    return True


def can_view(actor, target_type, target):
    """Reading an item's effective price follows the same scope as editing it, or finance."""
    if target is None:
        return False
    return can_price(actor, target_type, target) or rbac.can(actor, rbac.Action.VIEW_FINANCE, target.makerspace_id)


def _covers_pool(actor, pool):
    from apps.machines.role_scope import EXEMPT, covers_machine, covers_type, manage_scope_for

    if pool.machine_id:
        return covers_machine(actor, pool.machine)
    if pool.machine_type_id:
        return covers_type(actor, pool.makerspace_id, pool.machine_type)
    # A pool with no affinity is shared by every machine: only an unscoped manager prices it.
    return manage_scope_for(actor, pool.makerspace_id) is EXEMPT
