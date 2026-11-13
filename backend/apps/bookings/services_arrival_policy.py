"""Shared arrival matrix; called by Booking.save inside resource -> booking locks.

BK-B staff edits/undo use ordinary saves, so these guards also protect that lane
without replacing its admission, cancellation provenance or notification policy.
"""

from datetime import timedelta
from uuid import uuid4

from django.utils import timezone

from .exceptions import BookingInvalidTransition


def arrival_eligible(booking, *, now):
    return (booking.status == "confirmed" and booking.space.is_active
            and booking.starts_at - timedelta(minutes=30) <= now <= booking.ends_at)


def require_no_arrival(booking):
    if booking.arrived_at is not None:
        raise BookingInvalidTransition("Reverse the recorded arrival first.")


def prepare_booking_save(booking, kwargs):
    """Enforce edits against persisted state, and rotate credentials atomically.

    Projection-only saves from arrival/correction do not change lifecycle facts.
    Returning the additional fields keeps callers' update_fields saves atomic.
    """
    if not booking.pk:
        return
    old = type(booking).objects.only("starts_at", "ends_at", "status", "arrived_at", "space_id").get(pk=booking.pk)
    moved = (old.starts_at, old.ends_at) != (booking.starts_at, booking.ends_at)
    changed_status = old.status != booking.status
    now = getattr(booking, "_arrival_clock", None) or timezone.now()
    if moved:
        from .services_schedule import member_can_cancel
        old.space = booking.space
        require_no_arrival(old)
        if not member_can_cancel(old, now=now):
            raise BookingInvalidTransition("The booking reschedule cutoff has passed.")
        if booking.ends_at <= booking.starts_at or booking.starts_at <= now + timedelta(
            hours=booking.space.cancellation_cutoff_hours,
        ):
            raise BookingInvalidTransition("New time must be after the reschedule cutoff.")
    if changed_status and booking.status in ("cancelled", "no_show"):
        require_no_arrival(old)
    if (changed_status and old.status in ("completed", "rejected", "no_show")
            and booking.status in ("pending", "confirmed")):
        raise BookingInvalidTransition("Terminal bookings cannot be reopened.")
    # A future BK-B exact restore must not resurrect source credentials/arrival.
    rotate = moved or (changed_status and (booking.status == "cancelled" or old.status == "cancelled"))
    if rotate:
        booking.checkin_token = uuid4()
        booking.arrived_at = None
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = list(set(kwargs["update_fields"]) | {"checkin_token", "arrived_at"})
