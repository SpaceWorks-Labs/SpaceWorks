"""Resource-only workspace discovery through the always-present source registry."""

from .booking_authority import active_grants
from .booking_permissions import PERMISSIONS


def has_grant_authority(actor, *, makerspace_ids=None):
    rows = active_grants(actor)
    if makerspace_ids is not None:
        rows = rows.filter(makerspace_id__in=makerspace_ids)
    return rows.exists()


def granted_booking_entries(actor, *, makerspace_ids=None):
    rows = active_grants(actor)
    if makerspace_ids is not None:
        rows = rows.filter(makerspace_id__in=makerspace_ids)
    return [{"space_id": row.space_id, "makerspace_id": row.makerspace_id,
             "makerspace_slug": row.makerspace.slug, "name": row.space.name,
             "source": "booking_grant", "permissions": sorted(set(row.permissions) & set(PERMISSIONS))}
            for row in rows.order_by("space__name", "pk")]
