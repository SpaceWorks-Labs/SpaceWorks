from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied

from apps.accounts.staff_identity import has_staff_role, is_person
from apps.accounts import rbac
from apps.accounts.models import User
from apps.makerspaces.origin_scope import (
    object_in_staff_origin_scope,
    staff_origin_scope_allows,
)


def active_user(user):
    # `must_change_password` (the generated first-run credential) must NOT be able to reach
    # protected staff/admin endpoints over the API before rotating — only the
    # IsAuthenticated rotation path (/auth/change-password, /auth/me) stays open.
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and user.access_status == User.AccessStatus.ACTIVE
        and not getattr(user, "must_change_password", False)
    )


class IsActiveStaff(BasePermission):
    def has_permission(self, request, view):
        return active_user(getattr(request, "user", None)) and staff_origin_scope_allows(
            request,
            view,
        )

    def has_object_permission(self, request, view, obj):
        return object_in_staff_origin_scope(request, obj)


class IsActiveSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return active_user(user) and (
            user.is_superuser or user.role == User.Role.SUPERADMIN
        ) and staff_origin_scope_allows(request, view)

    def has_object_permission(self, request, view, obj):
        return object_in_staff_origin_scope(request, obj)


def require_action(user, action, makerspace_id):
    if not rbac.can(user, action, makerspace_id):
        raise PermissionDenied()


def require_user_access_mutation(actor, target):
    # A person holding staff roles is managed through the staff-role lifecycle, so the
    # community restrict/restore switch never silently removes someone's staff access.
    if not is_person(target) or has_staff_role(target):
        raise PermissionDenied(
            "Staff and platform accounts cannot use community access changes."
        )
