"""Single live authority policy for booking staff operations and discovery."""

from django.db.models import F, Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.makerspaces.capability_eligibility import feature_enabled_servable_ids
from apps.makerspaces.guards import require_module
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable, servable_q

from .booking_permissions import PERMISSIONS, VIEW
from .models import BookableSpace
from .models_staff_grants import BookingSpaceStaffGrant


def active_account(actor):
    return bool(actor and getattr(actor, "is_authenticated", False) and actor.is_active
                and actor.access_status == "active" and not actor.is_tenant_dump_stub
                and type(actor).objects.filter(pk=actor.pk, is_active=True,
                    access_status="active", is_tenant_dump_stub=False).exists())


def active(actor):
    return active_account(actor) and not actor.must_change_password and type(actor).objects.filter(
        pk=actor.pk, must_change_password=False).exists()


def _servable(space):
    return is_servable(space.makerspace) and module_enabled(space.makerspace, "bookings")


def active_grants(actor, *, makerspace_id=None, space_ids=None):
    from apps.makerspaces.module_registry import module_available
    rows = BookingSpaceStaffGrant.objects.none()
    # Forced-password login can discover authority; writes still require active().
    if (not active_account(actor) or getattr(actor, "account_kind", None) != "member"
            or not module_available("bookings")):
        return rows
    rows = BookingSpaceStaffGrant.objects.filter(
        user=actor, revoked_at__isnull=True, space__makerspace_id=F("makerspace_id"),
        makerspace__enabled_modules__contains=["bookings"],
    ).filter(servable_q("makerspace")).select_related("makerspace", "space")
    if makerspace_id is not None:
        rows = rows.filter(makerspace_id=makerspace_id)
    if space_ids is not None:
        rows = rows.filter(space_id__in=space_ids)
    # Batch live configuration/recovery checks through the canonical feature
    # policy. Calling feature_enabled per tenant adds recovery queries at login.
    enabled_ids = feature_enabled_servable_ids(rows.values("makerspace_id"), "bookings.staff_grants")
    valid = Q()
    for permission in PERMISSIONS:
        valid |= Q(permissions__contains=[permission])
    return rows.filter(valid, makerspace_id__in=enabled_ids)


def can_manage_grants(actor, space):
    return (active(actor) and _servable(space)
            and rbac.can(actor, rbac.Action.MANAGE_BOOKINGS, space.makerspace_id))


def can(actor, space, permission):
    if not active(actor) or not _servable(space) or permission not in (*PERMISSIONS, VIEW, None):
        return False
    if can_manage_grants(actor, space):
        return True
    if permission is None:
        return False
    rows = active_grants(actor, makerspace_id=space.makerspace_id).filter(space=space)
    if permission != VIEW:
        rows = rows.filter(permissions__contains=[permission])
    return rows.exists()


def require(actor, space, permission):
    require_module(space.makerspace, "bookings")
    if not can(actor, space, permission):
        raise PermissionDenied()


def require_tenant(actor, makerspace, *, action=rbac.Action.MANAGE_BOOKINGS):
    require_module(makerspace, "bookings")
    if (not active(actor) or not is_servable(makerspace)
            or not rbac.can(actor, action, makerspace.pk)):
        raise PermissionDenied()


def spaces_for(actor, permission, queryset=None):
    from apps.makerspaces.module_registry import module_available
    rows = BookableSpace.objects.all() if queryset is None else queryset
    if not active(actor) or not module_available("bookings"):
        return rows.none()
    managers = rbac.scope_by_action(actor, rbac.Action.MANAGE_BOOKINGS, BookableSpace.objects.all())
    allowed = Q(pk__in=managers.values("pk"))
    if permission in (*PERMISSIONS, VIEW):
        grants = active_grants(actor)
        if permission != VIEW:
            grants = grants.filter(permissions__contains=[permission])
        allowed |= Q(pk__in=grants.values("space_id"))
    elif permission is not None:
        return rows.none()
    return rows.filter(allowed, servable_q("makerspace"),
                       makerspace__enabled_modules__contains=["bookings"])


def visible_spaces(actor, queryset=None):
    rows = BookableSpace.objects.all() if queryset is None else queryset
    visible = rbac.scope_by_visibility_or_action(actor, rbac.Action.MANAGE_BOOKINGS, rows)
    allowed = spaces_for(actor, VIEW, rows)
    return rows.filter(Q(pk__in=visible.values("pk")) | Q(pk__in=allowed.values("pk")))


def get_space(actor, pk, permission=None):
    space = get_object_or_404(visible_spaces(actor, BookableSpace.objects.select_related("makerspace")), pk=pk)
    require(actor, space, permission)
    return space


def permissions_for(actor, space):
    if can_manage_grants(actor, space):
        return list(PERMISSIONS)
    return sorted({value for values in active_grants(actor).filter(space=space).values_list("permissions", flat=True)
                   for value in values if value in PERMISSIONS})
