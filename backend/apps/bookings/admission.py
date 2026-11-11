"""Ordinary reservation admission; callers hold the resource lock."""

from django.utils.translation import gettext
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
    _refuse_machine_time_booking_off(space)
    _refuse_room_outage(space, booking)
    _refuse_machine_under_repair(space, booking)
    if booking.member_id:
        # Reload account standing rather than trusting a caller's cached relation.
        booking.member = type(booking.member).objects.get(pk=booking.member_id)
        require_booking_account(booking.member, space.makerspace)
        _require_machine_person(space, booking, now)
    _require_certification(space, booking.member, actor, override_reason)
    _validate(booking)
    enforce_booking_rules(space, booking.starts_at, booking.ends_at, now)
    if booking.ends_at <= now:
        raise ValidationError({"ends_at": gettext("End time must be in the future.")})
    if check_conflict is None:
        check_conflict = booking.status == Booking.Status.CONFIRMED
    if check_conflict and confirmed_overlap(
        space, booking.starts_at, booking.ends_at, exclude=booking.pk,
    ):
        raise BookingConflict("This space is already booked for that time.")


def room_outages_apply(space):
    """Room outages are a layer of `bookings.room_maintenance`: switched off (or the maintenance
    app removed), a retained outage row no longer refuses, warns or shows."""
    from apps.makerspaces.platform import feature_enabled
    from apps.separability.registry import runtime_active
    return runtime_active("maintenance") and feature_enabled(space.makerspace, "bookings.room_maintenance")


def machine_repairs_apply(space):
    """A linked machine's repair window applies only while the space runs the machines module."""
    from apps.makerspaces.platform import module_enabled
    return bool(space.machine_id) and module_enabled(space.makerspace, "machines")


def machine_time_booking_off(space):
    """Decision 230 (d): a machine-linked resource takes bookings only while `machines.time_booking` is on
    (admission, readiness and the busy overlay all ask this one predicate)."""
    from apps.makerspaces.platform import feature_enabled
    return bool(space.machine_id) and not feature_enabled(space.makerspace, "machines.time_booking")


def _refuse_machine_time_booking_off(space):
    if machine_time_booking_off(space):
        from apps.makerspaces.guards import feature_off
        raise feature_off("machines.time_booking", "Machine time booking is switched off here.")


def _refuse_room_outage(space, booking):
    """L16 (#128 C-6b): a room out of service in block mode refuses overlapping bookings."""
    if room_outages_apply(space) and booking.starts_at and booking.ends_at:
        from apps.maintenance.repairs.room_outages import refuse_if_blocked
        refuse_if_blocked(space, booking.starts_at, booking.ends_at)


def _refuse_machine_under_repair(space, booking):
    """Trace gap 19: a bookable machine out of service for repair refuses overlapping bookings."""
    if machine_repairs_apply(space) and booking.starts_at and booking.ends_at:
        from apps.machines.booking_gate import refuse_if_under_repair
        from apps.machines.models import Machine
        machine = Machine.objects.filter(pk=space.machine_id).only("id", "status", "is_active").first()  # current status, not a cached one
        if machine is not None and not machine.is_active:
            # Machines audit 0.12.0: a retired machine's time is not bookable.
            raise BookingInvalidTransition("This machine is retired and cannot be booked.")
        if machine is not None:
            refuse_if_under_repair(machine, booking.starts_at, booking.ends_at)


def _require_machine_person(space, booking, now):
    """Machines audit 0.12.0 (223(d)/(k)): booking a machine's time is machine use, so the minors
    rule and a guest pass's machine mode apply as they do to sessions and jobs. Lazy imports:
    bookings never depends on the machines app."""
    if not machine_repairs_apply(space):
        return
    from apps.makerspaces.guest_pass_queries import active_pass_for
    from apps.makerspaces.minors_guard import require_minor_clearance
    from apps.makerspaces.models import MakerspaceMembership
    member, makerspace, at = booking.member, space.makerspace, booking.starts_at or now
    require_minor_clearance(member, makerspace, "machine")
    if MakerspaceMembership.objects.filter(makerspace=makerspace, user=member, status="active").exists():
        return
    guest_pass = active_pass_for(member, makerspace, at)
    if guest_pass is not None:
        from apps.machines.guest_access import require_guest_machine
        machine_type = space.machine_type if space.machine_type_id else space.machine.machine_type
        require_guest_machine(guest_pass, member, makerspace, machine_type=machine_type, surface="job", at=at)


def require_feature(space, key):
    from apps.makerspaces.platform import feature_enabled
    if not feature_enabled(space.makerspace, key):
        from apps.makerspaces.guards import feature_off
        raise feature_off(key, "This bookings feature is turned off.")
