"""Updated calendar invites after an event changes (#169, lane L6): one bounded fan-out task."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)
LIMIT = 2000


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_invite_updates_task(self, event_id, sequence):
    from .models import Event, EventRegistration
    from .registration_invites import update_envelope
    event = Event.objects.filter(pk=event_id, status=Event.Status.PUBLISHED).first()
    if event is None or event.calendar_sequence != sequence:
        return 0  # a later change has its own task; only the newest sequence is sent
    sent = 0
    rows = (EventRegistration.objects.filter(event=event, status="registered", member__isnull=False)
            .select_related("event__makerspace", "member", "registered_via_makerspace").order_by("pk")[:LIMIT])
    for registration in rows.iterator(chunk_size=200):
        try:
            sent += update_envelope(registration) is not None
        except Exception:
            logger.warning("event_invite_update_failed", extra={"registration_id": registration.pk})
    return sent
