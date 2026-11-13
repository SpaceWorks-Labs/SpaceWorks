"""Query-level machine list scoping and the Machines-tab capability (split from `access.py`).

Re-exported from `apps.machines.access`.
This path is pinned by ``tenant_migration.authority_guards.AUTHORIZATION_SOURCES``.
"""
from apps.accounts import rbac
from apps.accounts.models import User
from apps.accounts.rbac import Action

from . import role_scope
from .access_core import FULL, MANAGE, _active_membership_makerspace_ids, is_active_member
from .models import MachineOperator, MachineType


def scope_machines_for_actor(actor, queryset):
    """Machines the actor may see: union of MANAGE_MACHINES labs, type-managed
    machines (via managing_action), and explicitly-assigned operator machines.
    Starts from membership + archived scope (via rbac helpers)."""
    from django.db.models import Q

    if actor is None or not getattr(actor, "is_authenticated", False):
        return queryset.none()

    manage_scope = rbac.makerspaces_for_action(actor, Action.MANAGE_MACHINES)
    if manage_scope is rbac.ALL:
        # ALL is only the action-level tenant scope. A superadmin who is also an
        # explicit member of a makerspace may still have a machine-scoped role there,
        # so resolve every tenant represented by this multi-makerspace queryset through
        # role_scope.manage_scopes_for (via scoped_q) instead of treating ALL as exempt.
        manage_scope = set(queryset.values_list("makerspace_id", flat=True).distinct())

    # Was `Q(makerspace_id__in=manage_scope)`: holding MANAGE_MACHINES listed every machine
    # in the space. Now the grant only reaches the linked types/machines, resolved at query
    # level so a scoped list stays one query.
    q = role_scope.scoped_q(actor, manage_scope) if manage_scope else Q(pk__in=[])

    for action in _managing_actions():
        # Direct grants only -- see `role_scope.makerspaces_granting_directly`. Using the
        # implication-expanding scope here would list every printer to a laser-scoped role.
        tscope = role_scope.makerspaces_granting_directly(actor, action)
        if tscope is rbac.ALL:
            q |= Q(machine_type__managing_action=action)
        elif tscope:
            q |= Q(machine_type__managing_action=action, makerspace_id__in=tscope)

    member_ms = _active_membership_makerspace_ids(actor)
    if member_ms:
        op_ids = MachineOperator.objects.filter(
            user=actor, machine__makerspace_id__in=member_ms
        ).values_list("machine_id", flat=True)
        q |= Q(pk__in=list(op_ids))

    return queryset.filter(q).distinct()


def scope_manageable_machines_for_actor(actor, queryset):
    """Machines whose warranty the actor may manage, entirely at query level.

    Includes machine admins, type managers, and active manage/full operators.
    Operate-only assignments are deliberately excluded from warranty reporting.
    """
    from django.db.models import Q

    if actor is None or not getattr(actor, "is_authenticated", False):
        return queryset.none()

    queryset = rbac.scope_by_makerspace(actor, queryset)
    manage_scope = rbac.makerspaces_for_action(actor, Action.MANAGE_MACHINES)
    if manage_scope is rbac.ALL:
        # This queryset may span makerspaces. Normalize the action-level ALL sentinel to
        # its concrete tenant ids, then let scoped_q's plural resolver decide EXEMPT vs
        # role-linked machine scope independently for each one.
        manage_scope = set(queryset.values_list("makerspace_id", flat=True).distinct())

    q = role_scope.scoped_q(actor, manage_scope) if manage_scope else Q(pk__in=[])
    for action in _managing_actions():
        type_scope = role_scope.makerspaces_granting_directly(actor, action)
        if type_scope is rbac.ALL:
            q |= Q(machine_type__managing_action=action)
        elif type_scope:
            q |= Q(
                machine_type__managing_action=action,
                makerspace_id__in=type_scope,
            )

    if (
        getattr(actor, "is_active", False)
        and getattr(actor, "access_status", None) == User.AccessStatus.ACTIVE
    ):
        member_ms = _active_membership_makerspace_ids(actor)
        operator_ids = MachineOperator.objects.filter(
            user=actor,
            access_level__in=(MANAGE, FULL),
            machine__makerspace_id__in=member_ms,
        ).values_list("machine_id", flat=True)
        q |= Q(pk__in=operator_ids)

    return queryset.filter(q).distinct()


def can_see_machines(actor, makerspace_id):
    """Server-derived capability for the Machines tab within one makerspace.

    A MANAGE_MACHINES holder whose role is scoped to nothing must not get the tab: it
    would render an always-empty list and every action inside it would 403. Holding a
    link is what earns the tab, not holding the action.
    """
    if rbac.can(actor, Action.MANAGE_MACHINES, makerspace_id):
        scope = role_scope.manage_scope_for(actor, makerspace_id)
        if scope is role_scope.EXEMPT or any(scope):
            return True
    for action in _managing_actions():
        if rbac.can(actor, action, makerspace_id) and role_scope.grants_directly(
            actor, makerspace_id, action
        ):
            return True
    if is_active_member(actor, makerspace_id):
        return MachineOperator.objects.filter(
            user=actor, machine__makerspace_id=makerspace_id
        ).exists()
    return False


def _managing_actions():
    return list(
        MachineType.objects.exclude(managing_action="")
        .values_list("managing_action", flat=True)
        .distinct()
    )
