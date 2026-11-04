"""Room outages and bookings (#93, #128 C-6b).

While a room is out of service in BLOCK mode (the default), new bookings that overlap the
outage are refused through the bookings admission policy; in WARN mode they go through.
Existing bookings inside the window are listed for staff, who cancel each one (a staff
cancellation owes the full amount, #72) or keep it; the bookers are told by email.
"""

from django.db.models import Q
from django.utils import timezone

from apps.bookings.exceptions import BookingConflict


def open_outage(room):
    from apps.maintenance.models import RoomOutage
    return RoomOutage.objects.filter(room=room, ended_at__isnull=True).first()


def _overlaps(outage, starts_at, ends_at):
    back = outage.expected_back_at
    return ends_at > outage.started_at and (back is None or starts_at < back)


def refuse_if_blocked(room, starts_at, ends_at):
    """The admission seam: a blocking outage refuses an overlapping new booking."""
    outage = open_outage(room)
    if outage is not None and outage.mode == outage.Mode.BLOCK and _overlaps(outage, starts_at, ends_at):
        raise BookingConflict("This room is out of service for that time.")


def affected_bookings(outage):
    from apps.bookings.models import Booking
    window = Q(ends_at__gt=max(outage.started_at, timezone.now()))
    if outage.expected_back_at is not None:
        window &= Q(starts_at__lt=outage.expected_back_at)
    return (Booking.objects.filter(space_id=outage.room_id, status__in=("pending", "confirmed"))
            .filter(window).order_by("starts_at", "id"))
