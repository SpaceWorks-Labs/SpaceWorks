"""Bulk per-machine capability flags for list endpoints (split from `access.py`).

Re-exported from `apps.machines.access`. Must stay in step with the single-machine
checks in `access_core`; the two disagreeing is how a button renders enabled and then 403s.
This path is pinned by ``tenant_migration.authority_guards.AUTHORIZATION_SOURCES``.
"""
from apps.accounts import rbac
from apps.accounts.rbac import Action

from . import role_scope
from .access_core import _CAPABILITY_KEYS, FULL, MANAGE, is_active_member
from .models import MachineOperator


def capabilities_for_machines(actor, machines):
    """Bulk per-machine capabilities in O(1) queries regardless of fleet size.

    Memoizes the makerspace-level rbac decisions (MANAGE_MACHINES + each type's
    managing_action + live membership are constant across machines in the same
    makerspace) and fetches every operator level in a single query, so a list
    endpoint never re-derives capabilities per row. Requires the machines to have
    `machine_type` loaded (the list view select_relates it) so no extra type query
    fires. Falls back to False for an anonymous actor.
    """
    machines = list(machines)
    empty = {key: False for key in _CAPABILITY_KEYS}
    if actor is None or not getattr(actor, "is_authenticated", False):
        return {m.pk: dict(empty) for m in machines}

    op_levels = dict(
        MachineOperator.objects.filter(machine__in=machines, user=actor)
        .values_list("machine_id", "access_level")
    )
    # Resolved once for the whole batch. Per-machine now (a role can be scoped to some of
    # a makerspace's machines), so it cannot be memoized by makerspace like the rest —
    # but the lookup it feeds is pure, so this stays two queries for any fleet size.
    scopes = role_scope.manage_scopes_for(actor, {m.makerspace_id for m in machines})
    manage_cache, type_cache, member_cache = {}, {}, {}

    def _manage(ms_id):
        if ms_id not in manage_cache:
            manage_cache[ms_id] = rbac.can(actor, Action.MANAGE_MACHINES, ms_id)
        return manage_cache[ms_id]

    def _type_mgr(ms_id, action):
        action = (action or "").strip()
        if not action:
            return False
        key = (ms_id, action)
        if key not in type_cache:
            # Must match `_type_manager` exactly, direct-grant check included: the bulk
            # path feeds the list view's per-row capability flags, and the two disagreeing
            # is how a button renders enabled and then 403s.
            type_cache[key] = rbac.can(actor, action, ms_id) and (
                role_scope.grants_directly(actor, ms_id, action)
            )
        return type_cache[key]

    def _member(ms_id):
        if ms_id not in member_cache:
            member_cache[ms_id] = is_active_member(actor, ms_id)
        return member_cache[ms_id]

    result = {}
    for machine in machines:
        ms_id = machine.makerspace_id
        in_scope = _manage(ms_id) and role_scope.scope_covers_machine(
            scopes.get(ms_id, role_scope.NOTHING), machine
        )
        admin = in_scope or _type_mgr(
            ms_id, getattr(machine.machine_type, "managing_action", "")
        )
        level = op_levels.get(machine.pk) if _member(ms_id) else None
        can_edit = admin or level in {MANAGE, FULL}
        result[machine.pk] = {
            "can_operate": can_edit or level is not None,
            "can_edit": can_edit,
            "can_delegate": admin or level == FULL,
            "can_retire": admin or level == FULL,
            "can_unretire": admin,
        }
    return result
