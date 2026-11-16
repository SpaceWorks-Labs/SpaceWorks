"""Read-only track visibility for a limited co-organizer (decision 221(i) follow-up).

A co-organizer holding `manage_team` limited to some tracks must still see those tracks, or the
invite form's "Limit to tracks" picker has nothing to offer. They hold no `manage_hackathon`, so
the definition editor stays closed; only this read-only listing opens, and only to the tracks
their own live grants cover (every track when one of their `manage_team` sources is event-wide).
"""

from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from apps.events.contributions.authority import active_entitlements


def readable_track_ids(actor, event):
    """`None` = every track of the event; a set = only those tracks. 403 without a live `manage_team` source."""
    sources = list(active_entitlements(event_id=event.pk).filter(
        Q(event=event) | Q(series_id=event.series_id, series__isnull=False),
        grant__user=actor, permissions__contains=["manage_team"],
    ))
    if not sources:
        raise PermissionDenied()
    if any(not source.track_ids for source in sources):
        return None
    return {track_id for source in sources for track_id in source.track_ids}
