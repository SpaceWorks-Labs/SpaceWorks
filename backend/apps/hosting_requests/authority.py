"""Who may invite a makerspace, and when "Join <organization>" may be offered.

No new action or role: a makerspace invitation needs ``MANAGE_MAKERSPACE`` in that
makerspace (the subdomain-request gate) and an organization invitation needs the
``MANAGE_ORGANIZATION_MEMBERS`` governance action. Organization governance belongs to
member accounts only, so a staff Space Manager can invite but never offers Join.

Lock order everywhere in this app: makerspace -> organization -> organization membership
-> hosting row. These helpers take only the organization and membership locks.
"""

from django.http import Http404
from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.makerspaces.servability import servable_queryset
from apps.organizations import governance
from apps.organizations.access import (
    lock_governance_membership, require_governance, visible_organizations,
)
from apps.organizations.models import Organization, OrganizationMakerspace


def resolve_makerspace_inviter(actor, makerspace_id):
    makerspace = servable_queryset().filter(pk=makerspace_id).first()
    if makerspace is None:
        raise Http404()
    if not rbac.can(actor, rbac.Action.MANAGE_MAKERSPACE, makerspace.pk):
        raise PermissionDenied()
    return makerspace


def offerable_owner_organization(actor, makerspace):
    """The makerspace's active owner organization, if the actor governs it; else None.

    A non-member account cannot hold organization governance, so the organization is
    not even locked for staff or platform actors.
    """
    if not governance.member_account(actor):
        return None
    owner_id = (
        OrganizationMakerspace.objects.filter(
            makerspace=makerspace, relationship=OrganizationMakerspace.Relationship.OWNER,
        )
        .values_list("organization_id", flat=True)
        .first()
    )
    if owner_id is None:
        return None
    organization = Organization.objects.select_for_update().filter(
        pk=owner_id, is_active=True,
    ).first()
    if organization is None:
        return None
    try:
        lock_governance_membership(
            actor, organization, governance.MANAGE_ORGANIZATION_MEMBERS,
        )
    except PermissionDenied:
        return None
    return organization


def resolve_organization_inviter(actor, organization_id):
    if not visible_organizations(actor).filter(pk=organization_id).exists():
        raise Http404()
    if not governance.member_account(actor):
        raise PermissionDenied()
    organization = Organization.objects.select_for_update().filter(
        pk=organization_id, is_active=True,
    ).first()
    if organization is None:
        raise Http404()
    lock_governance_membership(actor, organization, governance.MANAGE_ORGANIZATION_MEMBERS)
    return organization


def require_organization_reader(actor, organization_id):
    """Unlocked read check for listing: the same authority, without row locks."""
    organization = visible_organizations(actor).filter(pk=organization_id, is_active=True).first()
    if organization is None:
        raise Http404()
    if not governance.member_account(actor):
        raise PermissionDenied()
    require_governance(actor, organization, governance.MANAGE_ORGANIZATION_MEMBERS)
    return organization
