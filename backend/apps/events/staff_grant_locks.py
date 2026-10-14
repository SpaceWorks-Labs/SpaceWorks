"""Stabilize delegation authority without changing organizer/RBAC semantics."""

from apps.accounts.models import User
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership

from .models import EventOrganizer, EventSeriesOrganizer


def lock_authority(actor, target):
    if actor is None:
        return None
    # The domain target and tenant are already locked. Organization parents precede
    # their users/links/memberships, matching organization administration. Local role
    # changes take the same tenant lock before touching memberships/roles.
    links = OrganizationMakerspace.objects.filter(makerspace_id=target.makerspace_id)
    events = EventOrganizer.objects.none()
    series = EventSeriesOrganizer.objects.none()
    if target._meta.model_name == "eventseries":
        series = EventSeriesOrganizer.objects.filter(series=target)
    else:
        events = EventOrganizer.objects.filter(event=target)
        if target.series_id:
            series = EventSeriesOrganizer.objects.filter(series_id=target.series_id)
    organization_ids = set(links.values_list("organization_id", flat=True))
    organization_ids.update(events.values_list("organization_id", flat=True))
    organization_ids.update(series.values_list("organization_id", flat=True))
    list(Organization.objects.select_for_update().filter(pk__in=organization_ids).order_by("pk"))
    # Protect account status/credentials while allowing FK KEY SHARE on invitee
    # identities; reciprocal redemptions must not deadlock on the two User rows.
    locked_actor = User.objects.select_for_update(no_key=True).filter(pk=actor.pk).first()
    if locked_actor is None:
        return None
    memberships = list(MakerspaceMembership.objects.select_for_update().filter(
        user=locked_actor, makerspace_id=target.makerspace_id,
    ).order_by("pk"))
    role_ids = [row.assigned_role_id for row in memberships if row.assigned_role_id]
    list(MakerspaceRole.objects.select_for_update().filter(pk__in=role_ids).order_by("pk"))
    list(links.select_for_update().order_by("pk"))
    list(events.select_for_update().order_by("pk"))
    list(series.select_for_update().order_by("pk"))
    list(OrganizationMembership.objects.select_for_update().filter(
        user=locked_actor, organization_id__in=organization_ids,
    ).order_by("pk"))
    return locked_actor
