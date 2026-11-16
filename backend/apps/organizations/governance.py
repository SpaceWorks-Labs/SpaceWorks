"""Organization-only authority, kept separate from makerspace RBAC grants."""

from apps.accounts.staff_identity import is_person
from apps.accounts.models import User
from apps.accounts.native_session import is_native_session


MANAGE_ORGANIZATION_PROFILE = "manage_organization_profile"
MANAGE_ORGANIZATION_MEMBERS = "manage_organization_members"
GOVERNANCE_ACTIONS = frozenset(
    {MANAGE_ORGANIZATION_PROFILE, MANAGE_ORGANIZATION_MEMBERS}
)


def live_account(actor):
    return bool(actor and getattr(actor, "is_authenticated", False)
                and actor.is_active and actor.access_status == User.AccessStatus.ACTIVE
                and not actor.is_tenant_dump_stub and actor.retired_at is None
                and actor.deletion_requested_at is None)


def member_account(actor):
    return live_account(actor) and is_person(actor)


def actions_for_membership(membership) -> set[str]:
    if (membership is None or membership.status != membership.Status.ACTIVE
            or not member_account(membership.user)):
        return set()
    value = membership.governance_actions
    if not isinstance(value, list):
        return set()
    return {
        action
        for action in value
        if isinstance(action, str) and action in GOVERNANCE_ACTIONS
    }


def actions_for(actor, organization) -> set[str]:
    if not live_account(actor) or is_native_session(actor):
        return set()
    from .access import is_superadmin
    if is_superadmin(actor):
        return set(GOVERNANCE_ACTIONS)
    if not member_account(actor) or not organization.is_active:
        return set()
    membership = organization.memberships.filter(
        user=actor,
        status="active",
    ).first()
    return actions_for_membership(membership)


def has_any_governance(actor) -> bool:
    if not live_account(actor) or is_native_session(actor):
        return False
    from .access import is_superadmin
    if is_superadmin(actor):
        return True
    if not member_account(actor):
        return False
    from apps.organizations.models import OrganizationMembership

    queryset = OrganizationMembership.objects.filter(
        user=actor,
        status=OrganizationMembership.Status.ACTIVE,
        organization__is_active=True,
    )
    from django.db.models import Q

    action_filter = Q()
    for action in GOVERNANCE_ACTIONS:
        action_filter |= Q(governance_actions__contains=[action])
    return queryset.filter(action_filter).exists()
