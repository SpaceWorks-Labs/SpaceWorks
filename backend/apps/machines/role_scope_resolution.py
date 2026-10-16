"""Resolve per-membership machine type scopes and test their coverage."""

from collections import defaultdict

from django.db.models import F, Q

from apps.accounts import rbac
from apps.accounts.rbac import Action

from apps.accounts.rbac_roles import additional_role_exists, stored_actions_for_membership
from apps.makerspaces.models import MakerspaceMembership

from .models_membership_scope import MembershipMachineTypeScope


# Scoping does not restrict this actor here. A distinct object rather than None/True so a
# caller cannot confuse "unrestricted" with "restricted to nothing" -- the two are
# opposites and both are falsy in the shapes we would otherwise reach for.
EXEMPT = object()

# The fail-closed answer: a role that holds MANAGE_MACHINES but has no links.
NOTHING = (frozenset(), frozenset())


def _scope_for_membership(membership):
    """EXEMPT, a membership id to look links up for, or NOTHING."""
    if membership.assigned_role_id is None:
        return EXEMPT, None
    role = membership.assigned_role
    if role.makerspace_id != membership.makerspace_id:
        return NOTHING, None
    granted = role.granted_actions if isinstance(role.granted_actions, list) else []
    if Action.MANAGE_MAKERSPACE in granted:
        return EXEMPT, None
    additional = getattr(membership, "_additional_manage_machines", None)
    if additional is None:
        holds_machines = Action.MANAGE_MACHINES in stored_actions_for_membership(membership)
    else:
        holds_machines = Action.MANAGE_MACHINES in granted or additional
    if not holds_machines:
        return NOTHING, None
    return None, membership.pk


def manage_scopes_for(actor, makerspace_ids):
    """Map makerspace ids to EXEMPT or (type ids, empty machine ids)."""
    ids = {ms_id for ms_id in makerspace_ids if ms_id is not None}
    ids -= rbac.archived_makerspace_ids()
    if not ids or actor is None or not getattr(actor, "is_authenticated", False):
        return {}
    memberships = list(actor.makerspace_memberships.select_related("assigned_role").filter(
        status="active", makerspace_id__in=ids,
    ).annotate(_additional_manage_machines=additional_role_exists(
        actions=[Action.MANAGE_MACHINES],
    )))
    by_membership = manage_scopes_for_memberships(memberships)
    resolved = {row.makerspace_id: by_membership[row.pk] for row in memberships}
    superadmin = rbac._is_superadmin(actor)
    for ms_id in ids - set(resolved):
        resolved[ms_id] = EXEMPT if superadmin else NOTHING
    return resolved


def manage_scope_for(actor, makerspace_id):
    return manage_scopes_for(actor, [makerspace_id]).get(makerspace_id, NOTHING)


def manage_scopes_for_memberships(memberships):
    """Resolve any membership batch in at most two authority/scope queries.

    Each answer is keyed by PERSON, so two people holding the same built-in role
    cannot inherit each other's assigned machine types. Machine ids stay empty
    to preserve the stable two-set contract used by all machine consumers.
    """
    memberships = list(memberships)
    # A caller may provide plain memberships rather than select_related/prefetched
    # rows. Reload just those authority snapshots in ONE query, using Exists for
    # additional machine authority rather than introducing two lazy FK queries.
    unloaded = {
        row.pk for row in memberships if row.assigned_role_id is not None
        and not hasattr(row, "_additional_manage_machines")
        and ("assigned_role" not in row._state.fields_cache
             or "additional_roles" not in getattr(row, "_prefetched_objects_cache", {}))
    }
    snapshots = {}
    if unloaded:
        snapshots = {row.pk: row for row in MakerspaceMembership.objects.filter(
            pk__in=unloaded,
        ).select_related("assigned_role").annotate(
            _additional_manage_machines=additional_role_exists(actions=[Action.MANAGE_MACHINES]),
        )}
    resolved, scoped = {}, []
    for membership in memberships:
        if membership.pk in unloaded:
            membership = snapshots.get(membership.pk)
            if membership is None:
                continue
        answer, membership_id = _scope_for_membership(membership)
        if answer is not None:
            resolved[membership.pk] = answer
        else:
            scoped.append(membership_id)
    types = defaultdict(set)
    if scoped:
        for membership_id, type_id in MembershipMachineTypeScope.objects.filter(
            membership_id__in=scoped,
        ).filter(
            # Corrupt cross-tenant links must not confer authority.
            Q(machine_type__makerspace_id=F("membership__makerspace_id"))
            | Q(machine_type__makerspace__isnull=True, machine_type__is_builtin=True)
        ).values_list("membership_id", "machine_type_id"):
            types[membership_id].add(type_id)
    for membership_id in scoped:
        resolved[membership_id] = (frozenset(types[membership_id]), frozenset())
    for membership_id in unloaded - set(snapshots):
        resolved[membership_id] = NOTHING
    return resolved


def scope_covers_machine(scope, machine):
    """Whether a resolved scope reaches one machine. Pure -- no queries."""
    if scope is EXEMPT:
        return True
    type_ids, _ = scope
    return machine.machine_type_id in type_ids


def scope_covers_type(scope, machine_type):
    """Whether a resolved scope reaches a whole type.

    Used for creation, where there is no machine yet to check. A per-machine link cannot
    answer this -- it names a machine that does not exist -- so only a type link grants
    the right to add a machine of that type.
    """
    if scope is EXEMPT:
        return True
    if machine_type is None:
        return False
    type_ids, _ = scope
    type_id = getattr(machine_type, "pk", machine_type)
    return type_id in type_ids


def covers_machine(actor, machine):
    """Whether the actor's role scope reaches this machine. Assumes the grant is held."""
    return scope_covers_machine(manage_scope_for(actor, machine.makerspace_id), machine)


def covers_type(actor, makerspace_id, machine_type):
    """Whether the actor's role scope reaches this type. Assumes the grant is held."""
    return scope_covers_type(manage_scope_for(actor, makerspace_id), machine_type)
