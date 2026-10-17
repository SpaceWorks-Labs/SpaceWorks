"""Direct grants from valid membership role unions."""

from apps.accounts import rbac
from apps.accounts.rbac import Action

from .role_scope_resolution import EXEMPT, manage_scope_for


def is_machine_only(actor, makerspace_id):
    """Whether the actor's authority here is machine-scoped and NOTHING else.

    The printing arm reads the stored grant via ``role_grants_directly`` because
    ``MANAGE_MACHINES`` implies ``MANAGE_PRINTING`` in effective RBAC authority.
    """
    if not rbac.can(actor, Action.MANAGE_MACHINES, makerspace_id):
        return False
    if manage_scope_for(actor, makerspace_id) is EXEMPT:
        return False
    if role_grants_directly(actor, makerspace_id, Action.MANAGE_PRINTING):
        return False
    return not (
        rbac.can(actor, Action.VIEW_INVENTORY, makerspace_id)
        or rbac.can(actor, Action.MANAGE_MAKERSPACE, makerspace_id)
    )


def grants_directly(actor, makerspace_id, action):
    """Whether the actor's role grants ``action`` outright, rather than by implication.

    Stored grants distinguish genuine type-manager authority from authority merely
    implied by ``MANAGE_MACHINES``; tier 1 applies machine links to the latter.
    """
    if actor is None or not getattr(actor, "is_authenticated", False):
        return False
    if rbac._is_superadmin(actor):
        # Authority does not come from a role row, so no role can qualify it. Tier 1
        # already treats them as EXEMPT; agreeing here keeps the two consistent.
        return not rbac.superadmin_hidden_block_applies(actor, makerspace_id, action)
    return role_grants_directly(actor, makerspace_id, action)


def role_grants_directly(actor, makerspace_id, action):
    """Whether the actor's assigned ROLE stores ``action`` outright.

    Deliberately blind to superadmin status, unlike ``grants_directly``. This preserves
    a hidden-space superadmin's explicit machine-role narrowing.
    """
    if actor is None or not getattr(actor, "is_authenticated", False):
        return False
    from apps.accounts.rbac_memberships import _membership_for
    from apps.accounts.rbac_roles import stored_actions_for_membership

    membership = _membership_for(actor, makerspace_id)
    return action in stored_actions_for_membership(membership)


def organization_grants_directly(actor, makerspace_id, action):
    """Whether a usable organization membership stores ``action`` outright.

    This is intentionally separate from machine/type-manager authority: callers must
    opt into the narrow organization partition they can safely expose. The shared
    organization vocabulary rejects ``MANAGE_MACHINES`` before any implication is
    expanded, and the shared membership query supplies hard-hide/servability filtering.
    """
    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or action not in rbac.ORGANIZATION_GRANTABLE_ACTIONS
    ):
        return False
    values = rbac._organization_authority_memberships(
        actor, makerspace_ids=[makerspace_id]
    ).filter(granted_actions__contains=[action]).values_list(
        "granted_actions", flat=True
    )
    return any(isinstance(value, list) and action in value for value in values)


def makerspaces_granting_directly(actor, action):
    """Query-level twin of :func:`grants_directly`: ids, or ``rbac.ALL``."""
    if actor is None or not getattr(actor, "is_authenticated", False):
        return set()
    if rbac._is_superadmin(actor):
        return rbac.makerspaces_for_action(actor, action)
    memberships = actor.makerspace_memberships.filter(status="active")
    from apps.accounts.rbac_roles import direct_role_filter

    scope = set(
        memberships.filter(direct_role_filter([action])).values_list("makerspace_id", flat=True)
    )
    return rbac._exclude_archived_ids(scope)
