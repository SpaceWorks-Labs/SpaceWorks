"""Read and locked authorization helpers for global organizations."""

from rest_framework.exceptions import PermissionDenied

from apps.accounts.staff_identity import is_platform
from apps.accounts.models import User
from apps.organizations import governance
from apps.organizations.models import Organization, OrganizationMembership


def is_superadmin(actor) -> bool:
    return bool(
        governance.live_account(actor)
        and is_platform(actor)
        and (actor.is_superuser or actor.role == User.Role.SUPERADMIN)
    )


def visible_organizations(actor):
    queryset = Organization.objects.all()
    if is_superadmin(actor):
        return queryset
    if not governance.member_account(actor):
        return queryset.none()
    return queryset.filter(
        is_active=True,
        memberships__user=actor,
        memberships__status=OrganizationMembership.Status.ACTIVE,
    ).distinct()


def active_membership(actor, organization):
    if is_superadmin(actor):
        return None
    if not governance.member_account(actor):
        return None
    return OrganizationMembership.objects.filter(
        organization=organization,
        user=actor,
        status=OrganizationMembership.Status.ACTIVE,
        organization__is_active=True,
    ).first()


def require_governance(actor, organization, action):
    if action not in governance.actions_for(actor, organization):
        raise PermissionDenied()


def lock_governance_membership(actor, organization, action):
    """Recheck organization authority under the row changed by governance edits."""
    from apps.accounts.native_session import is_native_session
    if not governance.live_account(actor) or is_native_session(actor):
        raise PermissionDenied()
    if is_superadmin(actor):
        return None
    if not governance.member_account(actor):
        raise PermissionDenied()
    membership = OrganizationMembership.objects.select_for_update().filter(
        organization=organization,
        user=actor,
        status=OrganizationMembership.Status.ACTIVE,
        organization__is_active=True,
    ).first()
    if action not in governance.actions_for_membership(membership):
        raise PermissionDenied()
    return membership
