"""Booking start reminders as personal envelopes (no rooms; owner's chosen channels)."""

import logging

from apps.integrations.notification_links import local_link
from apps.integrations import email_templates
from apps.hardware_requests.notification_projection import addressed_context
from django.db import transaction

from .notification_sources import REMINDER_SOURCE
from .reminder_delivery import context_for

logger = logging.getLogger(__name__)


def emit_reminder(row, schedule, account):
    from apps.integrations.notification_outbox import emit
    makerspace = row.space.makerspace
    message = email_templates.render(makerspace, "bookings", "requester", "reminder", context_for(row))
    try:
        with transaction.atomic():
            envelope = emit(makerspace=makerspace, recipient=account, feature="bookings", stream="bookings", event="reminder",
                 audience="requester", dedup_key=f"bookings.reminder:{schedule.pk}:{row.pk}:{row.calendar_sequence}",
                 source_kind=REMINDER_SOURCE, source_id=str(row.pk), revision=str(row.calendar_sequence), subject=row,
                 context={**addressed_context(makerspace, "bookings", "reminder", "requester", context_for(row)),
                          "booking_id": row.pk, "offset_seconds": schedule.offset_seconds},
                 rendered={"subject": message["subject"], "text": message["text_body"], "html": message["html_body"],
                           "link": local_link(makerspace, "member", "bookings")})
            from .notification_owner_mailbox import notify_owner
            notify_owner(envelope)
    except Exception:
        logger.warning("booking_reminder_envelope_failed", extra={"booking_id": row.pk, "schedule_id": schedule.pk})
        return False
    return True
