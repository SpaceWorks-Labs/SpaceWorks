"""Per-machine authorization tiers for the Machines module (split from `access.py`).

The tier model is documented on the `access` barrel. Every function here is
re-exported from `apps.machines.access`; import from there, not from this file.
This path is pinned by ``tenant_migration.authority_guards.AUTHORIZATION_SOURCES``.
"""
from apps.accounts import rbac
from apps.accounts.models import User
from apps.accounts.rbac import Action

from . import role_scope
from .models import MachineOperator

FULL = MachineOperator.AccessLevel.FULL
MANAGE = MachineOperator.AccessLevel.MANAGE
OPERATE = MachineOperator.AccessLevel.OPERATE


def is_active_member(user, makerspace_id):
    """True if `user` is a live, active member of the makerspace (not merely a stored row)."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_tenant_dump_stub", False):
        return False
    if getattr(user, "access_status", None) != User.AccessStatus.ACTIVE:
        return False
    if not getattr(user, "is_active", False):
        return False
    return user.makerspace_memberships.filter(
        makerspace_id=makerspace_id, status="active"
    ).exists()


def _active_membership_makerspace_ids(user):
    if getattr(user, "is_tenant_dump_stub", False):
        return set()
    scope = set(
        user.makerspace_memberships.filter(status="active").values_list(
            "makerspace_id", flat=True
        )
    )
    return rbac._exclude_archived_ids(scope)


def operator_level(actor, machine):
    """The actor's access level on this machine, or None. Inert without live membership."""
    if not is_active_member(actor, machine.makerspace_id):
        return None
    row = MachineOperator.objects.filter(machine=machine, user=actor).first()
    return row.access_level if row else None


def _type_manager(actor, makerspace_id, machine_type):
    """Tier 2, and it must key on a DIRECTLY granted managing_action.

    `MANAGE_MACHINES` implies `MANAGE_PRINTING`, and the built-in 3d_printer type's
    managing_action is exactly that — so accepting an implied grant here would let a role
    scoped to lasers manage every printer in the lab, straight through tier 1's links.
    """
    action = (getattr(machine_type, "managing_action", "") or "").strip()
    if not action or not rbac.can(actor, action, makerspace_id):
        return False
    return role_scope.grants_directly(actor, makerspace_id, action)


def is_machine_admin(actor, machine):
    """Tier 1/2: in-scope MANAGE_MACHINES, or the machine type's manager.

    Not expressed via `can_create_machine` any more: creating needs a **type** link (there
    is no machine yet to name), while administering an existing machine is also satisfied
    by a per-machine link. Collapsing the two would make a machine-linked role unable to
    touch the very machine it was linked to.
    """
    if rbac.can(actor, Action.MANAGE_MACHINES, machine.makerspace_id) and (
        role_scope.covers_machine(actor, machine)
    ):
        return True
    return _type_manager(actor, machine.makerspace_id, machine.machine_type)


def is_full_operator(actor, machine):
    return operator_level(actor, machine) == FULL


# --- Roster (create) ---------------------------------------------------------

def can_create_machine(actor, makerspace_id, machine_type):
    """Registering a machine needs a TYPE link — a per-machine link cannot authorize it.

    A machine-scoped role was given one machine, not the right to add more of its kind.
    """
    if rbac.can(actor, Action.MANAGE_MACHINES, makerspace_id) and (
        role_scope.covers_type(actor, makerspace_id, machine_type)
    ):
        return True
    return _type_manager(actor, makerspace_id, machine_type)


# --- Per-machine operate / manage --------------------------------------------

def can_operate_machine(actor, machine):
    """Set status, log usage, log errors."""
    return can_manage_machine(actor, machine) or operator_level(actor, machine) is not None


def can_manage_machine(actor, machine):
    """Edit machine fields + upload/delete documents."""
    if is_machine_admin(actor, machine):
        return True
    return operator_level(actor, machine) in {MANAGE, FULL}


# --- Lifecycle ---------------------------------------------------------------

def can_retire_machine(actor, machine):
    """Retire (is_active=False): admin/type-manager OR a full operator."""
    return is_machine_admin(actor, machine) or is_full_operator(actor, machine)


def can_unretire_machine(actor, machine):
    """Reactivate: admin/type-manager ONLY (a machine's operators cannot self-resurrect it)."""
    return is_machine_admin(actor, machine)


# --- Operator delegation -----------------------------------------------------

def can_delegate_operators(actor, machine):
    '''View/delegate the operator roster: admin/type-manager or a full operator.'''
    return is_machine_admin(actor, machine) or is_full_operator(actor, machine)


_CAPABILITY_KEYS = (
    "can_operate", "can_edit", "can_delegate", "can_retire", "can_unretire",
)


def machine_capabilities(actor, machine):
    '''Return the server-derived actions available to the actor for this machine.'''
    return {
        'can_operate': can_operate_machine(actor, machine),
        'can_edit': can_manage_machine(actor, machine),
        'can_delegate': can_delegate_operators(actor, machine),
        'can_retire': can_retire_machine(actor, machine),
        'can_unretire': can_unretire_machine(actor, machine),
    }


def can_assign_operator(actor, machine, target_level, existing_level=None):
    """Whether `actor` may create/change an operator row at `target_level`.

    - Admin/type-manager: may set any level (including full).
    - A full operator: may assign/remove only operate|manage, and may NOT touch a full row.
      This prevents a full operator from minting more co-administrators.
    """
    if is_machine_admin(actor, machine):
        return True
    if not is_full_operator(actor, machine):
        return False
    if target_level == FULL or existing_level == FULL:
        return False
    return True
