"""Ordinary reservation admission; callers hold the resource lock."""

from rest_framework.exceptions import ValidationError

from .access import require_booking_account
from .exceptions import BookingConflict, BookingInvalidTransition
from .models import BookableSpace, Booking
from .services_schedule import confirmed_overlap


def admission_status(space):
    return (Booking.Status.CONFIRMED if space.approval_mode == BookableSpace.ApprovalMode.INSTANT
            else Booking.Status.PENDING)


def validate_admission(space, booking, *, now, actor, override_reason="", check_conflict=None):
    """Share creation policy with edits/undo without repricing an existing subject.

    Approval deliberately keeps its established, narrower validation semantics.
    Pending admissions occupy no window; a caller may request a conflict check
    when moving a pending reservation, matching the existing reschedule contract.
    """
    from .services_bookings import _require_certification, _validate
    from .services_rules import enforce_booking_rules

    booking.space = space
    if not space.is_active:
        raise BookingInvalidTransition("Inactive spaces cannot accept bookings.")
    if booking.member_id:
        # Reload account standing rather than trusting a caller's cached relation.
        booking.member = type(booking.member).objects.get(pk=booking.member_id)
        require_booking_account(booking.member, space.makerspace)
    _require_certification(space, booking.member, actor, override_reason)
    _validate(booking)
    enforce_booking_rules(space, booking.starts_at, booking.ends_at, now)
    if booking.ends_at <= now:
        raise ValidationError({"ends_at": "End time must be in the future."})
    if check_conflict is None:
        check_conflict = booking.status == Booking.Status.CONFIRMED
    if check_conflict and confirmed_overlap(
        space, booking.starts_at, booking.ends_at, exclude=booking.pk,
    ):
        raise BookingConflict("This space is already booked for that time.")


def require_feature(space, key):
    from apps.makerspaces.platform import feature_enabled
    if not feature_enabled(space.makerspace, key):
        raise ValidationError({"detail": "This bookings feature is disabled."})
