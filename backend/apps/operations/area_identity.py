"""Decision 242(h): named rows for an area manager's OWN area, without `view_audit`.

Identity-bearing report widgets (top members per room or machine) were gated on `view_audit`, which only the
Space Manager and Inventory Manager hold, so a Booking or Machine Manager could not contact the people using
their own rooms and machines. A definition keyed to one of the area actions below now also opens for the holder
of that action. Every other identity-bearing report keeps `view_audit`; the report builders themselves stay
scoped (machine types, spaces) exactly as before, and a superadmin still needs the PII window.
"""

from apps.accounts import rbac

AREA_NAMED_ACTIONS = frozenset({
    rbac.Action.MANAGE_BOOKINGS, rbac.Action.MANAGE_MACHINES, rbac.Action.MANAGE_EVENTS, rbac.Action.MANAGE_SHOP,
})


def named_rows_allowed(actor, definition, makerspace_id):
    """`view_audit`, or the report's own area action when that action is an area manager's."""
    if rbac.can(actor, rbac.Action.VIEW_AUDIT, makerspace_id):
        return True
    return definition.required_action in AREA_NAMED_ACTIONS and rbac.can(actor, definition.required_action, makerspace_id)
