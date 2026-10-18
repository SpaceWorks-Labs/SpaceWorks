"""Stabilize delegation authority without changing organizer/RBAC semantics."""

from apps.organizations.models import OrganizationMakerspace

from .models import EventOrganizer, EventSeriesOrganizer


def authority_sources(target):
    """Unlocked discovery; domain/tenant locks stabilize these bridge sets."""
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
    return links, events, series, organization_ids


def lock_authority(actor, target):
    from .programme_locks import _scopes, lock_authority as lock_programme_authority
    if _scopes.get() is not None:
        return lock_programme_authority(actor, target)
    from apps.makerspaces.resource_grant_locks import lock_tenant_authority
    links, events, series, organization_ids = authority_sources(target)
    return lock_tenant_authority(actor, target, extra_organization_ids=organization_ids,
                                 extra_links=(events, series))
