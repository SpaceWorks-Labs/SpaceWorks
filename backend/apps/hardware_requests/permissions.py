from rest_framework.permissions import BasePermission

from apps.accounts import rbac
from apps.accounts.models import User
from apps.makerspaces.origin_scope import staff_origin_scope_allows
from apps.tenant_rls.context import bind, current
from apps.tenant_rls.wrapper import release_connections


def _active_authenticated(user):
    return bool(
        getattr(user, "is_authenticated", False)
        and user.access_status == User.AccessStatus.ACTIVE
        and not getattr(user, "must_change_password", False)
    )


class CanReviewRequest(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not _active_authenticated(user) or not staff_origin_scope_allows(request, view):
            return False

        actions = (rbac.Action.ACCEPT_REQUEST, rbac.Action.REJECT_REQUEST)
        if rbac.makerspaces_for_actions(user, *actions):
            return True
        if current() is None:
            return False

        # The target binding can hide the caller's grants in other spaces. Check
        # the caller's authority alone so foreign and missing requests reach the
        # same scoped 404. The binding is restored before the view reads the request.
        release_connections()
        with bind(None):
            return bool(rbac.makerspaces_for_actions(user, *actions))


class CanViewHandoverQueue(BasePermission):
    """Accepted-requests (handover) queue: active staff who can issue somewhere.

    rbac.can() does not consider access_status, so a restricted/suspended staff user
    would otherwise pass a bare IsAuthenticated gate — this enforces active status too."""

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not _active_authenticated(user) or not staff_origin_scope_allows(request, view):
            return False
        return bool(rbac.makerspaces_for_action(user, rbac.Action.ISSUE_REQUEST))


class CanAssignBox(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not _active_authenticated(user) or not staff_origin_scope_allows(request, view):
            return False
        return bool(rbac.makerspaces_for_action(user, rbac.Action.ASSIGN_BOX))


class CanIssueRequest(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not _active_authenticated(user) or not staff_origin_scope_allows(request, view):
            return False
        return bool(rbac.makerspaces_for_action(user, rbac.Action.ISSUE_REQUEST))


class CanIssueDirectLoan(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not _active_authenticated(user) or not staff_origin_scope_allows(request, view):
            return False
        return bool(rbac.makerspaces_for_action(user, rbac.Action.ISSUE_DIRECT_LOAN))


class CanReturnRequest(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not _active_authenticated(user) or not staff_origin_scope_allows(request, view):
            return False
        return bool(rbac.makerspaces_for_action(user, rbac.Action.RETURN_REQUEST))


class CanReturnDirectLoan(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not _active_authenticated(user):
            return False
        return bool(rbac.makerspaces_for_action(user, rbac.Action.RETURN_REQUEST))
