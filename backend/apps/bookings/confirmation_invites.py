"""Calendar invites on booking confirmation emails (#169, built by lane L6).

The booking owner's email for a confirmed (or restored) booking attaches an `.ics`
invite with the booking's stable UID (`booking-<public token>@spaceworks`, the same as
the download and the feeds) and its calendar sequence, so a change re-sends a higher
SEQUENCE; a cancelled or rejected booking sends METHOD:CANCEL. The body gains "Add to
Google Calendar" and "Add to Outlook" links. Only the room name, times and location ride
along -- no booking token, note or other person's details.
"""

from apps.makerspaces.calendar_invites import calendar_links, invite_ics, with_calendar_links

CONFIRMED = frozenset({"created", "confirmed", "restored"})
CANCELLED = frozenset({"cancelled", "rejected"})


def _booking(envelope):
    from .models import Booking
    return (Booking.objects.select_related("space__makerspace")
            .filter(pk=envelope.source_id, member_id=envelope.recipient_id).first())


def invite_bytes(booking, *, cancel=False):
    space = booking.space
    return invite_ics(uid=f"booking-{booking.public_token}@spaceworks", title=space.name,
                      starts_at=booking.starts_at, ends_at=booking.ends_at, sequence=booking.calendar_sequence,
                      updated_at=booking.calendar_updated_at, cancel=cancel,
                      tentative=booking.status == "pending", location=space.location or "")


def attachments(envelope):
    from apps.integrations.inline_attachments import InlineAttachment
    if envelope.audience != "requester" or envelope.event not in CONFIRMED | CANCELLED:
        return ()
    booking = _booking(envelope)
    if booking is None or (envelope.event in CONFIRMED and booking.status not in ("confirmed", "pending")):
        return ()
    cancel = envelope.event in CANCELLED
    return (InlineAttachment("booking.ics", invite_bytes(booking, cancel=cancel),
                             f"text/calendar; charset=utf-8; method={'CANCEL' if cancel else 'PUBLISH'}"),)


def with_links(rendered, booking, event):
    if event not in CONFIRMED or booking.status != "confirmed":
        return rendered
    space = booking.space
    return with_calendar_links(rendered, calendar_links(title=space.name, starts_at=booking.starts_at,
                                                        ends_at=booking.ends_at, location=space.location or ""))


def register():
    from apps.integrations.inline_attachments import register_confirmation_attachments
    register_confirmation_attachments("bookings.lifecycle", attachments)
