"""Stabilize action-derived delegation authority after domain and tenant locks."""

from apps.accounts.models import User
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership


def lock_tenant_authority(actor, target, *, extra_organization_ids=(), extra_links=()):
    if actor is None:
        return None
    links = OrganizationMakerspace.objects.filter(makerspace_id=target.makerspace_id)
    organization_ids = set(links.values_list("organization_id", flat=True)) | set(extra_organization_ids)
    list(Organization.objects.select_for_update().filter(pk__in=organization_ids).order_by("pk"))
    locked_actor = User.objects.select_for_update(no_key=True).filter(pk=actor.pk).first()
    if locked_actor is None:
        return None
    memberships = list(MakerspaceMembership.objects.select_for_update().filter(
        user=locked_actor, makerspace_id=target.makerspace_id,
    ).order_by("pk"))
    role_ids = [row.assigned_role_id for row in memberships if row.assigned_role_id]
    list(MakerspaceRole.objects.select_for_update().filter(pk__in=role_ids).order_by("pk"))
    list(links.select_for_update().order_by("pk"))
    for rows in extra_links:
        list(rows.select_for_update().order_by("pk"))
    list(OrganizationMembership.objects.select_for_update().filter(
        user=locked_actor, organization_id__in=organization_ids,
    ).order_by("pk"))
    return locked_actor
