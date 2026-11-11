"""Audited, replace-only machine type and individual-machine assignments for one membership."""

from django.utils.translation import gettext
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.accounts.rbac_roles import additional_roles_prefetch, membership_roles
from apps.audit import services as audit
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.role_authority import _locked_actor_actions

from .member_scope_errors import MemberMachineScopeConflict
from .models import Machine, MachineType
from .models_membership_scope import MembershipMachineScope, MembershipMachineTypeScope


def assignable_machine_types(makerspace):
    return MachineType.objects.filter(
        Q(makerspace_id=makerspace.pk)
        | Q(makerspace__isnull=True, is_builtin=True)
    ).order_by("name", "id")


# Roles whose reach is narrowed per person: the Machine Manager (manage_machines) and the
# Technician (repairs/maintenance/service state). Any other role ignores the links.
SCOPED_ROLE_SLUGS = frozenset({"machine_manager", "technician"})


def assignable_machines(makerspace):
    return Machine.objects.filter(makerspace_id=makerspace.pk).order_by("name", "id")


def scoping_applies(membership):
    roles = membership_roles(membership)
    return bool(
        roles and roles[0].slug != "space_manager"
        and rbac.Action.MANAGE_MAKERSPACE not in (
            roles[0].granted_actions if isinstance(roles[0].granted_actions, list) else []
        )
        and any(role.slug in SCOPED_ROLE_SLUGS for role in roles)
    )


def current_scope(membership):
    return sorted(MembershipMachineTypeScope.objects.filter(
        membership=membership,
    ).values_list("machine_type_id", flat=True))


def current_machine_scope(membership):
    return sorted(MembershipMachineScope.objects.filter(
        membership=membership,
    ).values_list("machine_id", flat=True))


def _distinct_ids(value, field):
    if (not isinstance(value, (list, tuple))
            or any(type(item) is not int or item <= 0 for item in value)
            or len(set(value)) != len(value)):
        raise ValidationError({field: gettext("Use distinct positive integer ids.")})
    return set(value)


def validated_machine_ids(makerspace, machine_ids):
    """Distinct ids of machines that belong to ``makerspace`` (400 otherwise)."""
    ids = _distinct_ids(machine_ids, "machine_ids")
    allowed = set(assignable_machines(makerspace).filter(pk__in=ids).values_list("pk", flat=True))
    if ids - allowed:
        raise ValidationError({"machine_ids": gettext("Choose machines of this makerspace.")})
    return sorted(ids)


@transaction.atomic
def set_member_machine_scope(*, makerspace, membership, actor, machine_type_ids=None, machine_ids=None):
    """Makerspace FOR NO KEY UPDATE, then membership FOR UPDATE OF self.

    Replace-only for each list given; a list left as ``None`` is kept as it is. The reach
    is the union of the types and the machines; nothing listed reaches nothing.
    """
    makerspace = Makerspace.objects.select_for_update(no_key=True).get(pk=makerspace.pk)
    membership = (
        MakerspaceMembership.staff_tracks.select_for_update(of=("self",))
        .select_related("assigned_role").prefetch_related(additional_roles_prefetch())
        .get(pk=membership.pk, makerspace=makerspace)
    )
    if rbac.Action.MANAGE_MAKERSPACE not in _locked_actor_actions(actor, makerspace):
        raise PermissionDenied()
    if not scoping_applies(membership):
        raise MemberMachineScopeConflict()
    types_before, machines_before = current_scope(membership), current_machine_scope(membership)
    types_after, machines_after = types_before, machines_before
    if machine_type_ids is not None:
        requested = _distinct_ids(machine_type_ids, "machine_type_ids")
        allowed = set(assignable_machine_types(makerspace).values_list("pk", flat=True))
        if requested - allowed:
            raise ValidationError({"machine_type_ids": gettext("Unknown or foreign machine type ids.")})
        types_after = sorted(requested)
    if machine_ids is not None:
        machines_after = validated_machine_ids(makerspace, machine_ids)
    if types_before != types_after:
        MembershipMachineTypeScope.objects.filter(membership=membership).delete()
        MembershipMachineTypeScope.objects.bulk_create([
            MembershipMachineTypeScope(membership=membership, machine_type_id=type_id)
            for type_id in types_after
        ])
    if machines_before != machines_after:
        MembershipMachineScope.objects.filter(membership=membership).delete()
        MembershipMachineScope.objects.bulk_create([
            MembershipMachineScope(membership=membership, machine_id=machine_id)
            for machine_id in machines_after
        ])
    if (types_before, machines_before) != (types_after, machines_after):
        audit.record(actor, "staff.machine_scope_changed", makerspace=makerspace,
                     target=membership, meta={"membership_id": membership.pk,
                     "user_id": membership.user_id, "before": types_before, "after": types_after,
                     "machine_ids_before": machines_before, "machine_ids_after": machines_after})
    return types_after
