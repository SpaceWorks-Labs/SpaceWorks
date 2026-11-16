"""A permission class for member-only routes that must refuse claim sessions.

A permission class, not an `initial` override: `claim_pre_auth_guard` refuses any claim-reachable view that
overrides a framework lifecycle hook. This one runs after authentication (DRF checks permissions after it), and
its exact class + method is on the reviewed allowlist (`claim_pre_auth_allowlists`).
"""
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from apps.accounts.account_kind_guards import require_member_account


class MemberPersonOnly(BasePermission):
    def has_permission(self, request, view):
        if getattr(request, "claim_session", None) is not None:
            raise PermissionDenied()
        require_member_account(request.user)
        return True
