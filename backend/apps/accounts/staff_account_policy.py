"""One authority policy for staff roles: the staff-roles API, invitations and /control/.

One account per person (#62/#63): a staff role is a STAFF-TRACK membership row on a
person, never a separate account. Who may change one:

- the platform superadmin, in every space (Lane D's surface reaches the same routes);
- a Space Manager of the space, for every staff row except a Space Manager's: only the
  superadmin grants, changes or revokes the Space Manager role (#110, #111 Q14);
- nobody changes their own staff row (``self_change``).

Refusals carry a stable ``code`` beside ``detail`` (``StaffRoleRefused``) so the console
can explain them: ``last_manager``, ``self_change``, ``not_community_member``,
``quota_exceeded``, ``tenant_gated``, ``invite_email_mismatch``,
``space_manager_superadmin_only``, ``already_staff``.
"""

from django.utils.translation import gettext
from contextlib import contextmanager

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.accounts.models import User
from apps.accounts.platform_authority import is_platform_superadmin
from apps.accounts.rbac_roles import membership_roles
from apps.accounts.staff_identity import is_person
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.servability import is_servable

SPACE_MANAGER = "space_manager"
LAST_MANAGER, SELF_CHANGE, NOT_COMMUNITY_MEMBER = "last_manager", "self_change", "not_community_member"
QUOTA_EXCEEDED, TENANT_GATED, INVITE_EMAIL_MISMATCH = "quota_exceeded", "tenant_gated", "invite_email_mismatch"
SM_SUPERADMIN_ONLY, ALREADY_STAFF = "space_manager_superadmin_only", "already_staff"
_STATUS = {
    LAST_MANAGER: status.HTTP_409_CONFLICT, SELF_CHANGE: status.HTTP_403_FORBIDDEN,
    NOT_COMMUNITY_MEMBER: status.HTTP_409_CONFLICT, QUOTA_EXCEEDED: status.HTTP_409_CONFLICT,
    TENANT_GATED: status.HTTP_423_LOCKED, INVITE_EMAIL_MISMATCH: status.HTTP_403_FORBIDDEN,
    SM_SUPERADMIN_ONLY: status.HTTP_403_FORBIDDEN, ALREADY_STAFF: status.HTTP_409_CONFLICT,
}


class StaffRoleRefused(APIException):
    """A typed refusal: ``{"code": ..., "detail": ...}`` with the code's HTTP status."""

    def __init__(self, code, detail):
        self.status_code = _STATUS[code]
        super().__init__({"code": code, "detail": detail}, code=code)
        self.detail = {"code": code, "detail": detail}


def role_keys(membership):
    return [role.slug for role in membership_roles(membership)]


def _live(user):
    return bool(user is not None and getattr(user, "is_authenticated", False) and user.is_active
                and not user.is_tenant_dump_stub and user.retired_at is None and not user.must_change_password
                and user.access_status == User.AccessStatus.ACTIVE)


def manager_membership(actor, space):
    """The actor's active Space Manager staff row in this space, or None."""
    if not is_person(actor):
        return None
    row = MakerspaceMembership.staff_tracks.filter(user=actor, makerspace=space, status="active").first()
    return row if row and role_keys(row) == [SPACE_MANAGER] else None


def require_authority(actor, space, *, target=None, roles=None):
    """Refuse unless ``actor`` may manage staff roles in ``space`` (on ``target``, with
    ``roles``). Returns whether the actor may manage Space Managers (superadmin only)."""
    if not _live(actor) or not is_servable(space):
        raise PermissionDenied()
    superadmin = is_platform_superadmin(actor)
    if superadmin:
        if not rbac.can(actor, rbac.Action.MANAGE_MAKERSPACE, space.pk):
            raise PermissionDenied()
    elif not manager_membership(actor, space):
        raise PermissionDenied()
    if target is not None:
        if not is_person(target):
            raise PermissionDenied(gettext("Staff roles belong to a personal account."))
        if target.pk == actor.pk:
            raise StaffRoleRefused(SELF_CHANGE, gettext("You cannot change your own staff roles."))
        row = MakerspaceMembership.staff_tracks.filter(user=target, makerspace=space).first()
        if row is not None and SPACE_MANAGER in role_keys(row) and not superadmin:
            raise StaffRoleRefused(SM_SUPERADMIN_ONLY, gettext("Only the platform administrator manages Space Managers."))
    if roles is not None and any(role.slug == SPACE_MANAGER for role in roles) and not superadmin:
        raise StaffRoleRefused(SM_SUPERADMIN_ONLY, gettext("Only the platform administrator grants the Space Manager role."))
    return superadmin


def scoped_space(actor, space_id, *, lock=False):
    rows = rbac.scope_by_action(actor, rbac.Action.MANAGE_MAKERSPACE, Makerspace.objects.all(), "id")
    if lock:
        rows = rows.select_for_update(no_key=True)
    space = get_object_or_404(rows, pk=space_id)
    # Do not trust a request's cached principal after a concurrent change.
    actor = User.objects.get(pk=actor.pk)
    require_authority(actor, space)
    return space, actor


def target_row(space, membership_id, *, lock=False):
    """One staff-track row of this space (active or revoked); never a community row."""
    if lock:
        get_object_or_404(MakerspaceMembership.staff_tracks.select_for_update(of=("self",)),
                          pk=membership_id, makerspace=space)
    return get_object_or_404(MakerspaceMembership.staff_tracks.select_related("user"),
                             pk=membership_id, makerspace=space)


def protect_last_manager(space, membership):
    """Caller holds the tenant lock; lock the space's manager rows before counting.

    Every demotion, revocation and disable writer takes this same lock order.
    """
    managers = list(MakerspaceMembership.staff_tracks.select_for_update().filter(
        makerspace=space, assigned_role__slug=SPACE_MANAGER,
    ).order_by("pk"))
    if SPACE_MANAGER not in role_keys(membership):
        return
    active = [row for row in managers if row.status == "active" and row.user.is_active
              and row.user.access_status == User.AccessStatus.ACTIVE
              and not row.user.is_tenant_dump_stub and row.user.retired_at is None]
    if membership.pk in {row.pk for row in active} and len(active) <= 1:
        raise StaffRoleRefused(LAST_MANAGER, gettext("The last active Space Manager cannot be removed or demoted."))


@contextmanager
def staff_write(space_id):
    """The tenant-gate boundary every staff-role writer runs inside (``tenant_gated``)."""
    from apps.tenant_migration.gate_errors import SourceMigrationGateError
    from apps.tenant_migration.gate_runtime import tenant_write

    try:
        with tenant_write(space_id):
            yield
    except SourceMigrationGateError:
        raise StaffRoleRefused(TENANT_GATED, gettext("This makerspace is temporarily read-only.")) from None


def check_staff_quota(space):
    from apps.makerspaces import limits

    try:
        limits.check_quota(space, "staff", adding=1)
    except ValidationError as exc:
        raise StaffRoleRefused(QUOTA_EXCEEDED, gettext("This makerspace has reached its staff limit.")) from exc
