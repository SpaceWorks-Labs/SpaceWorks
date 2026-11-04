"""EVENTS on the public stats page (#170): listed public events and counts only.

Every row comes through the public event projection (`events.website_visibility`): public,
page live and LISTED. Invite-only events are left out too, so nothing here is an event the
public event list would not show. The upcoming list carries the public listing's card fields
only (title, dates, link token, cover); counts carry no names and pass suppression.
"""

from apps.makerspaces.editions import public_surface_available
from apps.makerspaces.platform import module_enabled

from .public_stats_period import in_window, suppressed

UPCOMING_LIMIT = 6


def _listed(makerspace):
    from apps.events.models import Event
    from apps.events.website_visibility import listed_q
    return Event.objects.filter(listed_q(), makerspace=makerspace).exclude(
        registration_audience=Event.RegistrationAudience.INVITE)


def _cover(event):
    from apps.inventory.public_image_storage import public_url
    key = event.image_key
    if event.series_id and "image_key" not in (event.series_override_fields or []):
        key = event.series.image_key
    return public_url(key) or None


def events_section(makerspace, window):
    if not (public_surface_available("events") and module_enabled(makerspace, "events")):
        return None
    from apps.events.models import Event, EventRegistration
    from apps.events.website_visibility import listed_events

    upcoming = (listed_events(makerspace).exclude(registration_audience=Event.RegistrationAudience.INVITE)
                .select_related("series").order_by("starts_at", "id"))
    held = in_window(_listed(makerspace).filter(
        status__in=(Event.Status.PUBLISHED, Event.Status.COMPLETED)), "starts_at", window)
    attendees = EventRegistration.objects.filter(event__in=held, status=EventRegistration.Status.ATTENDED)
    return {
        "upcoming": [{
            "public_token": str(event.public_token), "title": event.title,
            "starts_at": event.starts_at, "ends_at": event.ends_at, "image_url": _cover(event),
        } for event in upcoming[:UPCOMING_LIMIT]],
        "upcoming_count": suppressed(upcoming.count()),
        "held": suppressed(held.count()),
        "attendees": suppressed(attendees.count()),
    }


def events_metrics(section):
    return {"events.upcoming": section["upcoming_count"], "events.held": section["held"],
            "events.attendees": section["attendees"]}
