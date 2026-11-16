"""Batched event credential discovery, without manufacturing tenant actions."""

from django.db.models import F, Q

from .event_authority import active_grants
from .event_permissions import PERMISSIONS
from .models import Event, EventSeries


def has_grant_authority(user, *, makerspace_ids=None):
    grants = active_grants(user)
    if makerspace_ids is not None:
        grants = grants.filter(makerspace_id__in=makerspace_ids)
    return grants.exists()


def granted_event_entries(user, *, makerspace_ids=None):
    grants = active_grants(user)
    if makerspace_ids is not None:
        grants = grants.filter(makerspace_id__in=makerspace_ids)
    rows = list(grants.values("event_id", "series_id", "makerspace_id", "permissions"))
    if not rows:
        return []
    events = Event.objects.filter(
        Q(pk__in=[row["event_id"] for row in rows if row["event_id"]])
        | Q(series_id__in=[row["series_id"] for row in rows if row["series_id"]],
            series__makerspace_id=F("makerspace_id")),
    ).filter(makerspace_id__in={row["makerspace_id"] for row in rows}).select_related("makerspace").order_by("starts_at", "id")
    direct, series = {}, {}
    for row in rows:
        mapping, key = (direct, row["event_id"]) if row["event_id"] else (series, row["series_id"])
        mapping.setdefault(key, set()).update(set(row["permissions"]) & set(PERMISSIONS))
    entries = [{
        "event_id": event.pk, "series_id": event.series_id,
        "makerspace_id": event.makerspace_id, "makerspace_slug": event.makerspace.slug,
        "title": event.title, "source": "event_grant",
        "permissions": sorted(direct.get(event.pk, set()) | series.get(event.series_id, set())),
    } for event in events]
    series_rows = EventSeries.objects.filter(pk__in=series).select_related("makerspace").order_by("id")
    entries.extend({
        "event_id": None, "series_id": target.pk,
        "makerspace_id": target.makerspace_id, "makerspace_slug": target.makerspace.slug,
        "title": target.title, "source": "event_grant", "permissions": sorted(series[target.pk]),
    } for target in series_rows)
    return entries
