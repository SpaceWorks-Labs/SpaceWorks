"""Identity is narrower than effective actions for page ownership (P4).

Tenant lock order: write fence -> tenant -> account -> local membership/role ->
page -> namespace/storage. Never lock nullable joined FKs with select_for_update.
"""

from django.contrib.auth import get_user_model
from rest_framework.exceptions import PermissionDenied, NotFound
from django.shortcuts import get_object_or_404
from apps.accounts import rbac
from .models import Makerspace, MakerspaceMembership, MakerspaceRole
from .servability import is_servable


def reject_platform(actor):
    if (actor is None or not actor.is_authenticated or actor.is_superuser
            or actor.role == "superadmin" or actor.account_kind == "platform"):
        raise PermissionDenied("Page editing requires an authorized owner account.")


def lock_local_manager(owner_id, actor):
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    reject_platform(actor)
    if actor.account_kind == "staff" and actor.staff_makerspace_id != owner_id:
        raise NotFound()
    assert_write_allowed(owner_id)
    space = get_object_or_404(Makerspace.objects.select_for_update(), pk=owner_id)
    actor = get_user_model().objects.select_for_update().get(pk=actor.pk)
    reject_platform(actor)
    membership = MakerspaceMembership.objects.select_for_update().filter(
        makerspace=space, user=actor, status="active").first()
    role = (MakerspaceRole.objects.select_for_update().filter(pk=membership.assigned_role_id).first()
            if membership else None)
    if (not actor.is_active or actor.access_status != "active" or actor.must_change_password or actor.account_kind != "staff"
            or actor.staff_makerspace_id != space.pk or not is_servable(space)
            or role is None or role.slug != "space_manager" or role.makerspace_id != space.pk
            or not rbac.can(actor, rbac.MANAGE_MAKERSPACE, space)):
        raise PermissionDenied("Only this makerspace's local Space Manager may edit its page.")
    return space, actor


def lock_organization_governor(owner_id, actor):
    from apps.organizations.models import Organization
    from apps.organizations.access import lock_governance_membership
    from apps.organizations.governance import MANAGE_ORGANIZATION_PROFILE
    reject_platform(actor)
    organization = get_object_or_404(Organization.objects.select_for_update(), pk=owner_id,
                                    memberships__user=actor, memberships__status="active")
    actor = get_user_model().objects.select_for_update().get(pk=actor.pk)
    reject_platform(actor)
    if not actor.is_active or actor.access_status != "active" or actor.must_change_password or not organization.is_active:
        raise PermissionDenied()
    lock_governance_membership(actor, organization, MANAGE_ORGANIZATION_PROFILE)
    return organization, actor
