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
    _refuse_room_outage(space, booking)
    _refuse_machine_under_repair(space, booking)
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


def _refuse_room_outage(space, booking):
    """L16 (#128 C-6b): a room out of service in block mode refuses overlapping bookings."""
    from apps.separability.registry import runtime_active
    if runtime_active("maintenance") and booking.starts_at and booking.ends_at:
        from apps.maintenance.repairs.room_outages import refuse_if_blocked
        refuse_if_blocked(space, booking.starts_at, booking.ends_at)


def _refuse_machine_under_repair(space, booking):
    """Trace gap 19: a bookable machine out of service for repair refuses overlapping bookings."""
    if space.machine_id and booking.starts_at and booking.ends_at:
        from apps.machines.booking_gate import refuse_if_under_repair
        from apps.machines.models import Machine
        machine = Machine.objects.filter(pk=space.machine_id).only("id", "status").first()  # current status, not a cached one
        if machine is not None:
            refuse_if_under_repair(machine, booking.starts_at, booking.ends_at)


def require_feature(space, key):
    from apps.makerspaces.platform import feature_enabled
    if not feature_enabled(space.makerspace, key):
        raise ValidationError({"detail": "This bookings feature is disabled."})
