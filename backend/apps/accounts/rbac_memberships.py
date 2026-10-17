"""Membership-only RBAC identity helpers."""


from apps.accounts.rbac_roles import additional_roles_prefetch
from .membership_context import valid_membership_context
from apps.makerspaces.models import MakerspaceMembership


def membership_role(actor, makerspace_id):
    """Return the actor's MakerspaceMembership.role for this makerspace, or None."""
    membership = actor.makerspace_memberships.filter(
        status="active",
        makerspace_id=makerspace_id,
    ).first()
    return membership.role if valid_membership_context(membership) else None


def _membership_for(actor, makerspace_id) -> MakerspaceMembership | None:
    return actor.makerspace_memberships.select_related("assigned_role").prefetch_related(additional_roles_prefetch()).filter(
        status="active",
        makerspace_id=makerspace_id,
    ).first()


def _membership_is_space_manager(membership) -> bool:
    if not valid_membership_context(membership) or membership.user.account_kind != "staff":
        return False
    if membership.assigned_role_id is not None:
        role = membership.assigned_role
        return bool(
            role
            and role.makerspace_id == membership.makerspace_id
            and role.legacy_role == "space_manager"
        )
    return membership.role == MakerspaceMembership.Role.SPACE_MANAGER
