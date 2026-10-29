"""Lazy speaker-history adapter, so events can be absent or implemented later."""

from django.utils import timezone

from .platform import module_enabled
from .servability import is_servable


def speaking_contributions(profile):
    try:
        from apps.events.speaker_history import contributions_for
    except (ImportError, AttributeError):
        return []
    # The events-owned seam is responsible for account linkage and tenant provenance.
    # Do not infer an identity from a speaker's display name or free-text email.
    try:
        contributions = list(contributions_for(profile.membership.user, profile.membership.makerspace))
    except (ImportError, AttributeError):
        return []
    now = timezone.now()
    result = []
    for row in contributions:
        event = row.event
        if (event.status == "published" and event.is_public and event.listing == "listed"
                and event.page_state == "live"
                and row.occurred_at <= now
                and is_servable(event.makerspace) and module_enabled(event.makerspace, "events")):
            result.append(row)
    return result
