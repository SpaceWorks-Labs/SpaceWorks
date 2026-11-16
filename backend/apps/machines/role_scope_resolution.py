"""Resolve per-membership machine scopes (types plus individual machines) and test their coverage."""

from collections import defaultdict

from django.db.models import F, Q

from apps.accounts import rbac
from apps.accounts.rbac import Action
from apps.accounts.membership_context import valid_membership_context, valid_staff_membership_q

from apps.accounts.rbac_roles import additional_role_exists, stored_actions_for_membership
from apps.makerspaces.models import MakerspaceMembership

from .models_membership_scope import MembershipMachineScope, MembershipMachineTypeScope


# Scoping does not restrict this actor here. A distinct object rather than None/True so a
# caller cannot confuse "unrestricted" with "restricted to nothing" -- the two are
# opposites and both are falsy in the shapes we would otherwise reach for.
EXEMPT = object()

# The fail-closed answer: a role that holds MANAGE_MACHINES but has no links.
NOTHING = (frozenset(), frozenset())


def _scope_for_membership(membership):
    """EXEMPT, a membership id to look links up for, or NOTHING."""
    valid = getattr(membership, "_valid_account_context", None)
    if valid is None:
        valid = valid_membership_context(membership)
    if not valid or (not hasattr(membership, "_valid_account_context")
                     and membership.track != MakerspaceMembership.Track.STAFF):
        return NOTHING, None
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
    """Map makerspace ids to EXEMPT or (type ids, machine ids): reach is the union of both."""
    ids = {ms_id for ms_id in makerspace_ids if ms_id is not None}
    ids -= rbac.archived_makerspace_ids()
    if not ids or actor is None or not getattr(actor, "is_authenticated", False):
        return {}
    memberships = list(MakerspaceMembership.staff_tracks.select_related("assigned_role").filter(
        user_id=actor.pk, status="active", makerspace_id__in=ids,
    ).annotate(_valid_account_context=valid_staff_membership_q(), _additional_manage_machines=additional_role_exists(
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
    cannot inherit each other's assigned machines. The answer is the stable
    ``(type ids, machine ids)`` pair: a role reaches every machine of the listed
    types PLUS the listed individual machines; neither listed means nothing.
    """
    memberships = list(memberships)
    # A caller may provide plain memberships rather than select_related/prefetched
    # rows. Reload just those authority snapshots in ONE query, using Exists for
    # additional machine authority rather than introducing two lazy FK queries.
    unloaded = {row.pk for row in memberships if not hasattr(row, "_valid_account_context")}
    snapshots = {}
    if unloaded:
        snapshots = {row.pk: row for row in MakerspaceMembership.staff_tracks.filter(
            pk__in=unloaded,
        ).select_related("assigned_role").annotate(
            _valid_account_context=valid_staff_membership_q(),
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
    types, machines = link_reach(scoped)
    for membership_id in scoped:
        resolved[membership_id] = (frozenset(types[membership_id]), frozenset(machines[membership_id]))
    for membership_id in unloaded - set(snapshots):
        resolved[membership_id] = NOTHING
    return resolved


def link_reach(membership_ids):
    """Per-membership type ids and machine ids from the link tables, in two queries."""
    types, machines = defaultdict(set), defaultdict(set)
    if not membership_ids:
        return types, machines
    for membership_id, type_id in MembershipMachineTypeScope.objects.filter(
        membership_id__in=membership_ids,
    ).filter(
        # Corrupt cross-tenant links must not confer authority.
        Q(machine_type__makerspace_id=F("membership__makerspace_id"))
        | Q(machine_type__makerspace__isnull=True, machine_type__is_builtin=True)
    ).values_list("membership_id", "machine_type_id"):
        types[membership_id].add(type_id)
    for membership_id, machine_id in MembershipMachineScope.objects.filter(
        membership_id__in=membership_ids, machine__makerspace_id=F("membership__makerspace_id"),
    ).values_list("membership_id", "machine_id"):
        machines[membership_id].add(machine_id)
    return types, machines


def link_scope_for(actor, makerspace_id):
    """(type ids, machine ids) the actor's active staff row links, whatever its actions.

    Used by roles that are scoped without holding MANAGE_MACHINES (the Technician). A
    Space Manager is not scoped, so callers test EXEMPT separately; no row -> NOTHING.
    """
    if actor is None or not getattr(actor, "is_authenticated", False):
        return NOTHING
    row = MakerspaceMembership.staff_tracks.filter(
        user_id=actor.pk, status="active", makerspace_id=makerspace_id,
    ).annotate(_valid_account_context=valid_staff_membership_q()).first()
    if row is None or not row._valid_account_context:
        return NOTHING
    types, machines = link_reach([row.pk])
    return frozenset(types[row.pk]), frozenset(machines[row.pk])


def scope_covers_machine(scope, machine):
    """Whether a resolved scope reaches one machine. Pure -- no queries."""
    if scope is EXEMPT:
        return True
    type_ids, machine_ids = scope
    return machine.machine_type_id in type_ids or machine.pk in machine_ids


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
