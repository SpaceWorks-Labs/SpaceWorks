"""Audited, replace-only machine type assignments for one membership."""

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.accounts.rbac_roles import additional_roles_prefetch, membership_roles
from apps.audit import services as audit
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.role_authority import _locked_actor_actions

from .member_scope_errors import MemberMachineScopeConflict
from .models import MachineType
from .models_membership_scope import MembershipMachineTypeScope


def assignable_machine_types(makerspace):
    return MachineType.objects.filter(
        Q(makerspace_id=makerspace.pk)
        | Q(makerspace__isnull=True, is_builtin=True)
    ).order_by("name", "id")


def scoping_applies(membership):
    roles = membership_roles(membership)
    return bool(
        roles and roles[0].slug != "space_manager"
        and rbac.Action.MANAGE_MAKERSPACE not in (
            roles[0].granted_actions if isinstance(roles[0].granted_actions, list) else []
        )
        and any(role.slug == "machine_manager" for role in roles)
    )


def current_scope(membership):
    return sorted(MembershipMachineTypeScope.objects.filter(
        membership=membership,
    ).values_list("machine_type_id", flat=True))


@transaction.atomic
def set_member_machine_scope(*, makerspace, membership, actor, machine_type_ids):
    """Makerspace FOR NO KEY UPDATE, then membership FOR UPDATE OF self."""
    makerspace = Makerspace.objects.select_for_update(no_key=True).get(pk=makerspace.pk)
    membership = (
        MakerspaceMembership.objects.select_for_update(of=("self",))
        .select_related("assigned_role").prefetch_related(additional_roles_prefetch())
        .get(pk=membership.pk, makerspace=makerspace)
    )
    if rbac.Action.MANAGE_MAKERSPACE not in _locked_actor_actions(actor, makerspace):
        raise PermissionDenied()
    if not scoping_applies(membership):
        raise MemberMachineScopeConflict()
    if (not isinstance(machine_type_ids, (list, tuple))
            or any(type(value) is not int or value <= 0 for value in machine_type_ids)
            or len(set(machine_type_ids)) != len(machine_type_ids)):
        raise ValidationError({"machine_type_ids": "Use distinct positive integer ids."})
    requested = set(machine_type_ids)
    allowed = set(assignable_machine_types(makerspace).values_list("pk", flat=True))
    if requested - allowed:
        raise ValidationError({"machine_type_ids": "Unknown or foreign machine type ids."})
    before, after = current_scope(membership), sorted(requested)
    if before != after:
        MembershipMachineTypeScope.objects.filter(membership=membership).delete()
        MembershipMachineTypeScope.objects.bulk_create([
            MembershipMachineTypeScope(membership=membership, machine_type_id=type_id)
            for type_id in after
        ])
        audit.record(actor, "staff.machine_scope_changed", makerspace=makerspace,
                     target=membership, meta={"membership_id": membership.pk,
                     "user_id": membership.user_id, "before": before, "after": after})
    return after
