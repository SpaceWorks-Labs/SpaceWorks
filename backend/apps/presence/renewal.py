"""One renewal policy for the current-session hint and the locked writer."""
from datetime import timedelta

from apps.makerspaces.platform import module_enabled
from .policy import PresenceError


def renewal_expiry(row, space, *, now, duration_minutes, claim=None):
    if row is None or (claim and row.created_via_claim_session_id != claim.pk):
        raise PresenceError("session_required", "Check in before renewing.")
    if row.ended_at is not None and row.end_reason != "expired":
        raise PresenceError("session_ended", "Check in again after ending your presence.")
    if row.expires_at < now - timedelta(minutes=10):
        raise PresenceError("session_expired", "This session has expired. Check in again with your current location.")
    expiry = now + timedelta(minutes=duration_minutes)
    if row.event_registration_id:
        from apps.events.models import EventRegistration
        registration = EventRegistration.objects.select_related("event").get(pk=row.event_registration_id)
        if (not module_enabled(space, "events") or registration.status != "attended"
                or registration.event.status != "published"):
            raise PresenceError("event_session", "This event attendance is no longer current.")
        expiry = min(expiry, registration.event.ends_at)
    if claim:
        expiry = min(expiry, claim.absolute_expires_at)
    if expiry <= now:
        raise PresenceError("presence_expired", "The check-in authorization has expired.")
    return expiry
