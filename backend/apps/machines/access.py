"""Object-level authorization for the Machines module.

Builds on apps.accounts.rbac (which already enforces archived scoping).
Three tiers:
  1. MANAGE_MACHINES — full control of the machines the holder's ROLE is scoped to
     (`role_scope`), which for a space manager or superadmin is all of them.
  2. Type managers — hold a machine type's managing_action (3d_printer -> manage_printing).
  3. Per-machine operators (MachineOperator.access_level: operate/manage/full).

Tier 1 used to be makerspace-wide. It is now narrowed by `role_scope`, which asks which
machine types/machines the actor's role row was linked to and fails closed when it was
linked to none.

Tier 3 is untouched — an operator row already names one machine. Tier 2 keeps its own
breadth (a managing_action names one type, which is narrow by construction) but now
requires the action to be granted **directly**: `MANAGE_MACHINES` implies
`MANAGE_PRINTING`, and the built-in 3d_printer type's managing_action is exactly that, so
an implied grant here would have let a laser-scoped role manage every printer in the lab
straight through tier 1's links. See `role_scope.grants_directly`.

Every operator check re-verifies LIVE active membership, so a stale assignment row for a
removed/suspended member is inert and can never become a cross-tenant or stale escalation.

The implementation is split across three siblings, all re-exported here so
`from apps.machines import access` and `access.X` keep resolving:
`access_core` (the tiers and per-machine checks), `access_bulk` (list-view capability
flags) and `access_scoping` (query-level list scoping and the Machines tab). Each is
pinned by ``tenant_migration.authority_guards.AUTHORIZATION_SOURCES``.
"""
from .access_bulk import capabilities_for_machines
from .access_core import (
    _CAPABILITY_KEYS,
    FULL,
    MANAGE,
    OPERATE,
    _active_membership_makerspace_ids,
    _type_manager,
    can_assign_operator,
    can_create_machine,
    can_delegate_operators,
    can_manage_machine,
    can_operate_machine,
    can_retire_machine,
    can_unretire_machine,
    is_active_member,
    is_full_operator,
    is_machine_admin,
    machine_capabilities,
    operator_level,
)
from .access_scoping import (
    _managing_actions,
    can_see_machines,
    scope_machines_for_actor,
    scope_manageable_machines_for_actor,
)

__all__ = [
    "FULL", "MANAGE", "OPERATE",
    "can_assign_operator", "can_create_machine", "can_delegate_operators",
    "can_manage_machine", "can_operate_machine", "can_retire_machine",
    "can_see_machines", "can_unretire_machine", "capabilities_for_machines",
    "is_active_member", "is_full_operator", "is_machine_admin", "machine_capabilities",
    "operator_level", "scope_machines_for_actor", "scope_manageable_machines_for_actor",
]
