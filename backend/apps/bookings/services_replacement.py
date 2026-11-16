"""Replace a rejected or cancelled reservation through ordinary booking admission (decision 216).

The replacement is a NEW booking created by `services_bookings.create_booking`, so room
authority, active-member and waiver checks, availability, opening rules, quota,
certification, pricing (staff-confirmed) and approval mode all apply unchanged. The
original is never edited: its status, frozen price, `Payment`, settlement receipts and
audit history stay exactly as they were, so legitimate debt is preserved. A booking may
be replaced at most once (`Booking.replaces` is one-to-one), which also makes a racing
duplicate fail instead of creating two reservations.
"""

from django.db import transaction
from rest_framework.exceptions import NotFound

from apps.audit import services as audit

from .exceptions import BookingInvalidTransition
from .models import Booking

REPLACEABLE = (Booking.Status.REJECTED, Booking.Status.CANCELLED)


@transaction.atomic
def replace_booking(original, *, space, member, starts_at, ends_at, actor, price_confirmation,
                    note="", certification_override_reason=""):
    from .booking_authority import require
    from .services_bookings import _locked_booking, create_booking

    # Same lock order as every lifecycle transition: the original's room, then the booking.
    _original_space, locked = _locked_booking(original)
    if locked.space.makerspace_id != space.makerspace_id:
        raise NotFound()
    require(actor, locked.space, "manage_reservations")
    require(actor, space, "manage_reservations")
    if locked.status not in REPLACEABLE:
        raise BookingInvalidTransition("Only a rejected or cancelled booking can be replaced.")
    if Booking.objects.filter(replaces_id=locked.pk).exists():
        raise BookingInvalidTransition("This booking was already replaced.")
    replacement = create_booking(
        space, starts_at=starts_at, ends_at=ends_at, member=member, actor=actor, note=note,
        price_confirmation=price_confirmation, replaces=locked,
        certification_override_reason=certification_override_reason,
    )
    audit.record(actor, "booking.replacement_created", makerspace=space.makerspace, target=replacement,
                 meta={"booking_id": replacement.pk, "replaces_booking_id": locked.pk,
                       "replaced_status": locked.status, "status": replacement.status})
    return replacement
