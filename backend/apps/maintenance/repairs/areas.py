"""The three areas a repair belongs to, their switches, and who manages each (#102).

Each parent has its own switches (#128 C-9). Reporting works without repairs (notify
only); repairs need the parent's maintenance switch, because the repair job is L12's
work order, which lives under maintenance. Managers act in their own scope with no grant
(#102): a type-scoped Machine Manager on machines, the Inventory Manager on items, the
Booking Manager on rooms; the Space Manager everywhere.
"""

from django.utils.translation import gettext
from rest_framework.exceptions import NotFound

from apps.accounts import rbac
from apps.makerspaces.platform import feature_enabled

MACHINES, INVENTORY, ROOMS = "machines", "inventory", "rooms"
AREAS = (MACHINES, INVENTORY, ROOMS)
REPAIRS = {MACHINES: "machines.repairs", INVENTORY: "inventory.repairs", ROOMS: "bookings.room_repairs"}
REPORTING = {MACHINES: "machines.issue_reporting", INVENTORY: "inventory.issue_reporting",
             ROOMS: "bookings.issue_reporting"}
MAINTENANCE = {MACHINES: "machines.maintenance", INVENTORY: "inventory.maintenance",
               ROOMS: "bookings.room_maintenance"}
# Rooms get no To-Buy switch in release 2 (#137 Q-C3).
TOBUY = {MACHINES: "machines.tobuy", INVENTORY: "inventory.tobuy"}
LEDGER_DOMAIN = {MACHINES: "machines", INVENTORY: "inventory", ROOMS: "bookings"}
MANAGER_ACTION = {MACHINES: rbac.Action.MANAGE_MACHINES, INVENTORY: rbac.Action.EDIT_INVENTORY,
                  ROOMS: rbac.Action.MANAGE_BOOKINGS}
SUBJECT_AREA = {"machine": MACHINES, "inventory_product": INVENTORY, "inventory_asset": INVENTORY,
                "bookable_space": ROOMS}
SUBJECT_FIELD = {"machine": "machine", "inventory_product": "product", "inventory_asset": "asset",
                 "bookable_space": "room"}


def on(space, key):
    return feature_enabled(space, key)


def refuse(key):
    raise NotFound({"detail": gettext('{key} is switched off for this makerspace.').format(key=key), "code": "capability_disabled"})


def require(space, key):
    if not on(space, key):
        refuse(key)


def area_on(space, area):
    """Anything of this area's repairs surface is live (reporting or repairs)."""
    return on(space, REPAIRS[area]) or on(space, REPORTING[area])


def areas_on(space, keys):
    return [area for area in AREAS if area in keys and on(space, keys[area])]


def subject_model(subject_type):
    from apps.bookings.models import BookableSpace
    from apps.inventory.models import InventoryAsset, InventoryProduct
    from apps.machines.models import Machine
    return {"machine": Machine, "inventory_product": InventoryProduct, "inventory_asset": InventoryAsset,
            "bookable_space": BookableSpace}[subject_type]


def machine_type_id(row):
    """The machine type an issue, schedule or subject row is filed under (machines only)."""
    machine = getattr(row, "machine", None)
    return getattr(machine, "machine_type_id", None)


def manager_may(actor, space_id, subject_type, subject=None):
    """#102: the area's manager in their own scope; the Space Manager everywhere."""
    area = SUBJECT_AREA[subject_type]
    if area == MACHINES:
        if subject is None:
            return rbac.can(actor, rbac.Action.MANAGE_MACHINES, space_id)
        from apps.machines import access
        return access.can_manage_machine(actor, subject)
    return rbac.can(actor, MANAGER_ACTION[area], space_id)


def manages_any(actor, space_id):
    return any(rbac.can(actor, action, space_id) for action in MANAGER_ACTION.values())
