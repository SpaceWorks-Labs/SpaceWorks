"""Resolve a report actor's machine scope for builders that take ``actor`` (decision 224a)."""
from apps.accounts import rbac
from apps.machines import role_scope


def actor_machine_scope(actor, makerspace_id):
    """None = unscoped: no actor, the aggregate, an exempt holder, or admitted via another action.

    A type-scoped Machine Manager gets their scope; one with no links fails closed (NOTHING).
    """
    if actor is None or makerspace_id is None:
        return None
    if not rbac.can(actor, rbac.Action.MANAGE_MACHINES, makerspace_id):
        return None
    scope = role_scope.manage_scope_for(actor, makerspace_id)
    return None if scope is role_scope.EXEMPT else scope
