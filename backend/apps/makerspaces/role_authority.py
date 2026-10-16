"""Locked authority and validation for per-makerspace role mutations."""

from apps.accounts import rbac
from apps.accounts.rbac_roles import additional_roles_prefetch
from apps.accounts.models import User
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
from apps.organizations.models import (
    Organization,
    OrganizationMakerspace,
)

# The protected community role every activation path assigns (`roles.MEMBER_ROLE_DEFINITION`).
MEMBER_ROLE_SLUG = "member"


def _superadmin(actor):
    return actor.is_superuser or actor.role == User.Role.SUPERADMIN


def _locked_actor_actions(actor, makerspace):
    membership = (
        MakerspaceMembership.objects.prefetch_related(additional_roles_prefetch()).select_for_update(of=("self",))
        .select_related("assigned_role")
        .filter(makerspace=makerspace, user=actor, status="active")
        .first()
    )
    if membership and membership.assigned_role_id:
        membership.assigned_role = MakerspaceRole.objects.select_for_update().get(
            pk=membership.assigned_role_id
        )
    if _superadmin(actor) and makerspace.superadmin_access_enabled:
        return set(rbac.ROLE_GRANTABLE_ACTIONS)
    return rbac.actions_for_membership(membership) | _locked_organization_actions(
        actor, makerspace
    )


def _locked_organization_actions(actor, makerspace):
    """Revalidate organization authority under locks before role mutations."""
    # Resolve candidate parent/child ids without holding either row class. The locked
    # reads below then follow Django admin's parent-first save order.
    resolved_links = list(
        OrganizationMakerspace.objects
        .filter(makerspace=makerspace)
        .values_list("organization_id", "pk")
        .order_by("pk")
    )
    organization_ids = sorted(
        {organization_id for organization_id, _ in resolved_links}
    )
    if not organization_ids:
        return set()

    # Final organization-authority lock order: Organization rows (ascending pk),
    # then OrganizationMakerspace rows (ascending pk), then OrganizationMembership
    # rows (ascending pk). Django admin takes the same parent-before-child order.
    locked_organizations = list(
        Organization.objects.select_for_update()
        .filter(pk__in=organization_ids)
        .order_by("pk")
    )
    locked_organization_ids = [
        organization.pk for organization in locked_organizations
    ]
    locked_links = list(
        OrganizationMakerspace.objects.select_for_update()
        .filter(
            pk__in=[link_id for _, link_id in resolved_links],
            organization_id__in=locked_organization_ids,
            makerspace=makerspace,
        )
        .order_by("pk")
    )
    if not locked_links:
        return set()
    locked_link_ids = [link.pk for link in locked_links]
    locked_organization_ids = sorted(
        {link.organization_id for link in locked_links}
    )
    memberships = (
        rbac._organization_authority_memberships(
            actor, makerspace_ids=[makerspace.pk]
        )
        .filter(
            organization_id__in=locked_organization_ids,
            organization__makerspace_links__pk__in=locked_link_ids,
        )
        .select_for_update(of=("self",))
        .select_related("organization")
        .order_by("pk")
    )
    actions = set()
    for membership in memberships:
        actions.update(rbac.actions_for_organization_membership(membership))
    return actions


