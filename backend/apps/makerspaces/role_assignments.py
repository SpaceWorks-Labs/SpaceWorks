"""Locked role assignment and community-only roster delegation."""

from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.accounts.rbac_roles import additional_roles_prefetch
from apps.audit import services as audit
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole


def can_assign_roles(actor, makerspace, roles, target_membership=None):
    """Revalidate the actor ceiling against the complete union under locks."""
    from apps.makerspaces.role_authority import _locked_actor_actions, _superadmin
    from apps.makerspaces.role_membership_writes import validated_roles

    roles = list(roles)
    if (any(role.makerspace_id != makerspace.pk for role in roles)
            or (target_membership and target_membership.makerspace_id != makerspace.pk)):
        raise PermissionDenied()
    roles = validated_roles(
        target_membership or MakerspaceMembership(makerspace=makerspace), roles
    )
    actions = set().union(*(set(role.granted_actions) for role in roles))
    actor_actions = _locked_actor_actions(actor, makerspace)
    if rbac.Action.MANAGE_MAKERSPACE not in actor_actions:
        if (rbac.Action.MANAGE_MEMBERS not in actor_actions
                or [role.slug for role in roles] != ["member"]
                or (target_membership and rbac.actions_for_membership(target_membership))):
            raise PermissionDenied()
        return True
    if _superadmin(actor):
        return True
    if target_membership and rbac.Action.MANAGE_MAKERSPACE in rbac.actions_for_membership(target_membership):
        raise PermissionDenied()
    if rbac.Action.MANAGE_MAKERSPACE in actions or not actions <= (
        actor_actions - {rbac.Action.MANAGE_MAKERSPACE}
    ):
        raise PermissionDenied()
    return True


def can_assign_role(actor, makerspace, role, target_membership=None):
    return can_assign_roles(actor, makerspace, [role], target_membership)


def set_membership_roles(*, makerspace, actor, membership, roles):
    """Replace the complete role set, preserving the existing assignment lock order."""
    from apps.makerspaces.role_membership_writes import replace_membership_roles, validated_roles

    roles = list(roles)
    if membership.makerspace_id != makerspace.pk or any(
        role.makerspace_id != makerspace.pk for role in roles
    ):
        raise PermissionDenied()
    with transaction.atomic():
        makerspace = Makerspace.objects.select_for_update().get(pk=makerspace.pk)
        # Keep the pre-existing primary-role lock in its original position.
        # Additional roles are immutable and need no new row locks.
        requested_ids = {role.pk for role in roles}
        current_roles = list(MakerspaceRole.objects.filter(
            pk__in=requested_ids, makerspace=makerspace,
        ))
        if len(current_roles) != len(requested_ids):
            raise PermissionDenied()
        roles = validated_roles(membership, current_roles)
        primary = MakerspaceRole.objects.select_for_update().get(pk=roles[0].pk)
        roles[0] = primary
        membership = (
            MakerspaceMembership.objects.select_for_update(of=("self",))
            .select_related("assigned_role").prefetch_related(additional_roles_prefetch())
            .get(pk=membership.pk, makerspace=makerspace)
        )
        can_assign_roles(actor, makerspace, roles, target_membership=membership)
        changes = replace_membership_roles(
            membership=membership, roles=roles, actor=actor, reason="staff.roles_changed",
        )
        audit.record(actor, "staff.roles_changed", makerspace=makerspace,
                     target=membership.user, meta={"membership_id": membership.pk,
                     "before": changes["before"], "after": changes["after"],
                     "removed_machine_type_ids": changes["removed_machine_type_ids"]})
        return membership


def assign_role(*, makerspace, actor, membership, role):
    return set_membership_roles(
        makerspace=makerspace, actor=actor, membership=membership, roles=[role],
    )
