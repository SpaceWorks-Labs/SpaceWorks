"""Identity is narrower than effective actions for page ownership (P4).

Tenant lock order: write fence -> tenant -> local membership -> account -> role
-> page -> namespace/storage. Membership revocation's deferred account constraint
locks User at commit, so never hold User while waiting for its membership.
Never lock nullable joined FKs with select_for_update.
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
    membership = MakerspaceMembership.objects.select_for_update().filter(
        makerspace=space, user_id=actor.pk).first()
    actor = get_user_model().objects.select_for_update().get(pk=actor.pk)
    reject_platform(actor)
    role = (MakerspaceRole.objects.select_for_update().filter(pk=membership.assigned_role_id).first()
            if membership else None)
    _require_local_manager(space, actor, membership, role)
    return space, actor


def read_local_manager(owner_id, actor):
    """Same authority as lock_local_manager for reads: no tenant fence, no row locks."""
    reject_platform(actor)
    if actor.account_kind == "staff" and actor.staff_makerspace_id != owner_id:
        raise NotFound()
    space = get_object_or_404(Makerspace, pk=owner_id)
    membership = MakerspaceMembership.objects.filter(makerspace=space, user_id=actor.pk).first()
    actor = get_user_model().objects.get(pk=actor.pk)
    reject_platform(actor)
    role = MakerspaceRole.objects.filter(pk=membership.assigned_role_id).first() if membership else None
    _require_local_manager(space, actor, membership, role)
    return space, actor


def _require_local_manager(space, actor, membership, role):
    if (not actor.is_active or actor.access_status != "active" or actor.must_change_password or actor.account_kind != "staff"
            or actor.staff_makerspace_id != space.pk or not is_servable(space)
            or membership is None or membership.status != "active"
            or role is None or role.slug != "space_manager" or role.makerspace_id != space.pk
            or not rbac.can(actor, rbac.Action.MANAGE_MAKERSPACE, space.pk)):
        raise PermissionDenied("Only this makerspace's local Space Manager may edit its page.")


def lock_organization_governor(owner_id, actor):
    from apps.organizations.models import Organization
    from apps.organizations.access import lock_governance_membership
    from apps.organizations.governance import MANAGE_ORGANIZATION_PROFILE
    reject_platform(actor)
    organization = get_object_or_404(Organization.objects.select_for_update(), pk=owner_id)
    actor = get_user_model().objects.select_for_update().get(pk=actor.pk)
    reject_platform(actor)
    if not actor.is_active or actor.access_status != "active" or actor.must_change_password or not organization.is_active:
        raise PermissionDenied()
    lock_governance_membership(actor, organization, MANAGE_ORGANIZATION_PROFILE)
    return organization, actor


def read_organization_governor(owner_id, actor):
    """Same authority as lock_organization_governor for reads, without row locks."""
    from apps.organizations.models import Organization
    from apps.organizations.access import active_membership
    from apps.organizations.governance import MANAGE_ORGANIZATION_PROFILE, actions_for_membership
    reject_platform(actor)
    organization = get_object_or_404(Organization, pk=owner_id)
    actor = get_user_model().objects.get(pk=actor.pk)
    reject_platform(actor)
    if not actor.is_active or actor.access_status != "active" or actor.must_change_password or not organization.is_active:
        raise PermissionDenied()
    if MANAGE_ORGANIZATION_PROFILE not in actions_for_membership(active_membership(actor, organization)):
        raise PermissionDenied()
    return organization, actor
