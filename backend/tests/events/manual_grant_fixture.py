"""Legacy authority fixtures must now create a real manual source explicitly."""
from uuid import uuid4
from apps.events.models_staff_grants import EventStaffGrant
from apps.events.contributions.models_roles import EventGrantEntitlement
from tests.events.collab_helpers import make_staff


def create_manual_grant(**values):
    target = values.get("event") or values.get("series")
    if target is None and (values.get("event_id") or values.get("series_id")):
        from apps.events.models import Event, EventSeries
        target = Event.objects.get(pk=values["event_id"]) if values.get("event_id") else EventSeries.objects.get(pk=values["series_id"])
    if target is None:
        # No target at all: let the database scope constraint refuse the grant.
        return EventStaffGrant.objects.create(**values)
    if "granted_by" not in values and "granted_by_id" not in values:
        values["granted_by"] = make_staff(target.makerspace, username=f"grant-issuer-{uuid4().hex[:10]}")
    grant = EventStaffGrant.objects.create(**values)
    EventGrantEntitlement.objects.create(event_id=grant.event_id, series_id=grant.series_id,
        makerspace_id=grant.makerspace_id, grant=grant, source_kind="manual",
        permissions=grant.permissions, created_by_id=grant.granted_by_id,
        revoked_at=grant.revoked_at, revoked_by_id=grant.revoked_by_id)
    return grant


def bulk_manual_sources(grants):
    """Give bulk-created grants the live manual source that authority reads."""
    EventGrantEntitlement.objects.bulk_create([
        EventGrantEntitlement(event_id=grant.event_id, series_id=grant.series_id,
            makerspace_id=grant.makerspace_id, grant=grant, source_kind="manual",
            permissions=grant.permissions, created_by_id=grant.granted_by_id)
        for grant in grants
    ])
    return grants


def update_manual_permissions(grants, permissions):
    """Queryset form of a manual permission change: the source and its display union."""
    EventGrantEntitlement.objects.filter(grant__in=grants, source_kind="manual",
        revoked_at__isnull=True).update(permissions=permissions)
    return grants.update(permissions=permissions)
