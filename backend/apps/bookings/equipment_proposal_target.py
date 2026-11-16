"""Booking-owned target checks for an already-locked contextual proposal."""
from django.http import Http404

from apps.accounts.loan_context_identity import borrower_aliases
from apps.bookings import booking_authority, booking_permissions
from apps.bookings.models import Booking


def validate_booking(*, space, booking, makerspace_id, borrower, staff_actor=None):
    """Call after the source gate, bookable-space/maker/booking/borrower locks."""
    if (not space.is_active or space.makerspace_id != makerspace_id or booking.space_id != space.pk
            or booking.member_id is None or booking.status != Booking.Status.CONFIRMED):
        raise Http404
    if staff_actor is not None and not booking_authority.can(
        staff_actor, space, booking_permissions.MANAGE_RESERVATIONS,
    ):
        raise Http404
    try:
        aliases = borrower_aliases(borrower)
    except (ValueError, RuntimeError):
        raise Http404 from None
    if booking.member_id not in aliases:
        raise Http404
    return booking.member_id
