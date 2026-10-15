"""Staff-only QR resolve/arrival/correction, serialized with lifecycle services."""

from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from .confirmation_access import require_feature
from . import booking_authority
from .exceptions import BookingInvalidTransition
from .models import Booking
from .models_arrival import BookingCheckInEvent
from .services_arrival_policy import arrival_eligible
from .services_bookings import _audit, _locked_booking

PREFIX = "spaceworks-booking:"


def qr_value(booking):
    return PREFIX + str(booking.checkin_token)


def require_arrival_access(actor, space):
    booking_authority.require(actor, space, "check_in")
    require_feature(space.makerspace, "bookings.checkin")


def resolve_booking(space, credential, *, actor):
    require_arrival_access(actor, space)
    try:
        if not isinstance(credential, str) or not credential.startswith(PREFIX):
            raise NotFound()
        token = UUID(credential.removeprefix(PREFIX))
        if credential != PREFIX + str(token):
            raise NotFound()
    except (ValueError, AttributeError):
        raise NotFound() from None
    row = Booking.objects.select_related("space__makerspace", "member").filter(
        space=space, checkin_token=token,
    ).first()
    if row is None:
        raise NotFound()
    return row


@transaction.atomic
def confirm_arrival(space, credential, *, actor):
    candidate = resolve_booking(space, credential, actor=actor)
    space, booking = _locked_booking(candidate)
    booking.space = space
    require_arrival_access(actor, space)
    # Re-resolve after locking: cancellation/rescheduling may have rotated it.
    if qr_value(booking) != PREFIX + str(candidate.checkin_token):
        raise NotFound()
    now = timezone.now()
    if not arrival_eligible(booking, now=now):
        raise BookingInvalidTransition("Arrival requires a confirmed booking from 30 minutes before start through end.")
    if booking.arrived_at is not None:
        return booking
    booking.arrived_at = now
    booking.save(update_fields=["arrived_at"])
    event = BookingCheckInEvent.objects.create(booking=booking, actor=actor, action="arrived")
    _audit(space, actor, "booking.arrival_confirmed", event, {"booking_id": booking.pk})
    return booking


@transaction.atomic
def reverse_arrival(booking, *, actor):
    space, locked = _locked_booking(booking)
    locked.space = space
    require_arrival_access(actor, space)
    if locked.status not in ("confirmed", "completed") or locked.arrived_at is None:
        raise BookingInvalidTransition("Only an active confirmed or completed arrival can be reversed.")
    locked.arrived_at = None
    locked.save(update_fields=["arrived_at"])
    event = BookingCheckInEvent.objects.create(booking=locked, actor=actor, action="reversed")
    _audit(space, actor, "booking.arrival_reversed", event, {"booking_id": locked.pk})
    return locked
