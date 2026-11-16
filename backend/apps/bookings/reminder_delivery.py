"""Durable occurrence identity and booking-specific delivery-time reminder checks."""

from datetime import timezone as datetime_timezone

from django.utils import timezone

from apps.integrations.delivery_content import render
from apps.integrations.delivery_sources import DeliverySource, register
from apps.integrations.email_templates import render as render_template
from apps.integrations.email_templates_fablab import bookings_context
from apps.makerspaces.reminder_policy import reminder_offsets
from apps.operations.reminder_members import occurrence_subject
from .communication_recipients import recipient_account
from .notifications import _effective_toggle

SOURCE_KEY = "bookings.booking"


def stamp(value):
    return value.astimezone(datetime_timezone.utc).isoformat()


def identity(row):
    # The prefix is also used by unfinished_subjects, so an old revision's
    # completed claim cannot suppress a new occurrence with the same start.
    return occurrence_subject(f"{row.pk}:{row.calendar_sequence}", row.starts_at) + ":" + stamp(row.ends_at)


def snapshot(row, schedule):
    return {"makerspace_id": row.space.makerspace_id, "space_id": row.space_id,
            "booking_id": row.pk, "recipient_id": row.member_id,
            "starts_at": stamp(row.starts_at), "ends_at": stamp(row.ends_at),
            "calendar_sequence": row.calendar_sequence, "kind": schedule.kind,
            "offset_seconds": schedule.offset_seconds}


def context_for(row):
    with timezone.override(row.space.makerspace.timezone):
        return bookings_context(row, "reminder", next_steps="Your booking is coming up.")


def prepare(log):
    from .reminders import _bookings
    if log.source_kind != SOURCE_KEY or log.event != "reminder" or log.feature != "bookings":
        return False
    metadata = log.source_metadata
    if not isinstance(metadata, dict):
        return False
    row = _bookings(log.makerspace).filter(pk=log.source_id, member_id=log.recipient_id).first()
    if row is None:
        return False
    makerspace = row.space.makerspace
    log.makerspace = makerspace
    kind, offset = metadata.get("kind"), metadata.get("offset_seconds")
    if (kind != "starts" or type(offset) is not int or offset not in reminder_offsets(makerspace, "booking")
            or row.starts_at <= timezone.now() or not _effective_toggle(row)):
        return False
    expected = {"makerspace_id": makerspace.pk, "space_id": row.space_id, "booking_id": row.pk,
                "recipient_id": row.member_id, "starts_at": stamp(row.starts_at), "ends_at": stamp(row.ends_at),
                "calendar_sequence": row.calendar_sequence, "kind": kind, "offset_seconds": offset}
    if metadata != expected:
        return False
    account = recipient_account(makerspace, row.member_id, "reminder")
    if account is None:
        return False
    values = render_template(makerspace, "bookings", "requester", "reminder", context_for(row))
    render(log, to_email=account.email, **values)
    return True


def register_reminders():
    register(SOURCE_KEY, DeliverySource(prepare))
