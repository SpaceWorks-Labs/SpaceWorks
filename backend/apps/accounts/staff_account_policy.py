"""One lifecycle authority policy for HTTP, invitations and the control panel."""

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.accounts.models import User
from apps.accounts.rbac_roles import membership_roles
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.servability import is_servable


def manager_membership(actor, space):
    if actor.account_kind != "staff" or actor.staff_makerspace_id != space.pk:
        return None
    row = MakerspaceMembership.objects.filter(user=actor, makerspace=space, status="active").first()
    return row if row and role_keys(row) == ["space_manager"] else None


def role_keys(membership):
    return [role.slug for role in membership_roles(membership)]


def require_authority(actor, space, *, target=None, roles=None):
    if (not actor.is_authenticated or not actor.is_active or actor.is_tenant_dump_stub
            or actor.retired_at is not None or actor.must_change_password
            or actor.access_status != User.AccessStatus.ACTIVE or not is_servable(space)):
        raise PermissionDenied()
    platform = actor.account_kind == "platform" and actor.is_superuser
    if platform:
        if not space.superadmin_access_enabled or not rbac.can(actor, rbac.Action.MANAGE_MAKERSPACE, space.pk):
            raise PermissionDenied()
    elif not manager_membership(actor, space):
        raise PermissionDenied()
    can_manage_managers = platform or not space.superadmin_access_enabled
    if target is not None:
        if (target.account_kind != "staff" or target.staff_makerspace_id != space.pk
                or target.retired_at is not None or target.pk == actor.pk):
            raise PermissionDenied("Staff lifecycle changes cannot target your own account.")
        membership = MakerspaceMembership.objects.get(user=target, makerspace=space)
        if "space_manager" in role_keys(membership) and not can_manage_managers:
            raise PermissionDenied("Only the platform administrator may manage Space Managers while access is enabled.")
    if roles is not None and any(role.slug == "space_manager" for role in roles) and not can_manage_managers:
        raise PermissionDenied("Only the platform administrator may create or assign Space Managers while access is enabled.")
    return can_manage_managers


def scoped_space(actor, space_id, *, lock=False):
    rows = rbac.scope_by_action(actor, rbac.Action.MANAGE_MAKERSPACE, Makerspace.objects.all(), "id")
    if lock:
        rows = rows.select_for_update(no_key=True)
    space = get_object_or_404(rows, pk=space_id)
    # Do not trust a request's cached principal after a concurrent deactivation.
    actor = User.objects.get(pk=actor.pk)
    require_authority(actor, space)
    return space, actor


def target_account(space, user_id):
    return get_object_or_404(User, pk=user_id, account_kind="staff",
                           staff_makerspace=space, retired_at__isnull=True)


def protect_last_manager(space, membership):
    """Caller holds the tenant lock; lock its manager memberships before counting.

    All P3 demotion/deactivation writers take this same lock. There is no nullable
    joined FK in the locking query; role/user reads follow as ordinary queries.
    """
    managers = list(MakerspaceMembership.objects.select_for_update().filter(
        makerspace=space, assigned_role__slug="space_manager",
    ).order_by("pk"))
    if "space_manager" not in role_keys(membership):
        return
    active = [row for row in managers if row.status == "active" and row.user.is_active
              and row.user.access_status == User.AccessStatus.ACTIVE
              and not row.user.is_tenant_dump_stub and row.user.retired_at is None]
    if membership.pk in {row.pk for row in active} and len(active) <= 1:
        raise ValidationError({"detail": "The last active Space Manager cannot be removed or demoted."})
