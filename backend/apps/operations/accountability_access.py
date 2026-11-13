"""Decision 248 / IN8: who reads the accountability page, and how much of it.

`manage_members` (the people page) reads everything; the Inventory Manager (`view_inventory`) reads the overdue and
repeat-damage rows only, read-only. Handout-only desks are refused by the shared resolvers either way.
"""

from apps.accounts import rbac
from apps.admin_api.permissions import require_action
from apps.makerspaces.guards import require_module
from apps.operations import accountability


def accountability_for(user, makerspace_id):
    from .views_report_helpers import _makerspace_for_inventory_view, makerspace_for_members_view
    if rbac.can(user, rbac.Action.MANAGE_MEMBERS, makerspace_id):
        makerspace = makerspace_for_members_view(user, makerspace_id)
        require_action(user, rbac.Action.MANAGE_MEMBERS, makerspace.id)
        require_module(makerspace, "reports")
        return accountability.accountability_data(makerspace.id)
    makerspace = _makerspace_for_inventory_view(user, makerspace_id)
    require_action(user, rbac.Action.VIEW_INVENTORY, makerspace.id)
    require_module(makerspace, "reports")
    return accountability.inventory_read_view(makerspace.id)
