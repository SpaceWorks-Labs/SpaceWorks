"""Purpose-limited staff edits; transitions and money use their named services."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.forms_schema.validation import validate_answers

from . import booking_authority
from .admission import require_feature, validate_admission
from .exceptions import BookingInvalidTransition
from .services_bookings import _audit, _locked_booking, _refresh
from .services_schedule import member_can_cancel
from .services_arrival_policy import require_no_arrival


@transaction.atomic
def edit_booking_details(booking, *, actor, **changes):
    space, locked = _locked_booking(booking)
    booking_authority.require(actor, space, "manage_reservations")
    require_feature(space, "bookings.staff_tools")
    if locked.status not in ("pending", "confirmed"):
        raise BookingInvalidTransition("Only pending or confirmed bookings can be edited.")
    require_no_arrival(locked)
    unknown = set(changes) - {"note", "custom_answers"}
    if unknown or not changes:
        raise ValidationError({key: "This field cannot be edited." for key in sorted(unknown)}
                              or {"detail": "Provide a note or custom answers."})
    if "note" in changes:
        note = changes["note"]
        if not isinstance(note, str) or len(note) > 5000:
            raise ValidationError({"note": "Must be a string of at most 5000 characters."})
        locked.note = note.strip()
    if "custom_answers" in changes:
        locked.custom_answers = validate_answers(space.custom_form, changes["custom_answers"])
    locked.save(update_fields=sorted(changes))
    _audit(space, actor, "booking.details_edited", locked, {"changed_fields": sorted(changes)})
    return _refresh(locked)


def move_locked_booking(space, locked, *, actor, starts_at, ends_at, now):
    """Used by staff and owner moves, with one clock for both cutoff comparisons.

    Arrival checks and credential rotation share the resource/booking lock and
    the admission clock, so staff and owner moves enforce the same policy.
    """
    locked.space = space
    locked._arrival_clock = now
    require_no_arrival(locked)
    if not member_can_cancel(locked, now=now):
        raise BookingInvalidTransition("The booking reschedule cutoff has passed.")
    if locked.member_id is None:
        raise BookingInvalidTransition("An active booking owner is required to move a reservation.")
    old_start, old_end = locked.starts_at, locked.ends_at
    locked.starts_at, locked.ends_at = starts_at, ends_at
    validate_admission(space, locked, now=now, actor=actor, check_conflict=True)
    if starts_at <= now + timedelta(hours=space.cancellation_cutoff_hours):
        raise ValidationError({"starts_at": "New time must be after the reschedule cutoff."})
    locked.calendar_sequence += 1
    locked.calendar_updated_at = now
    locked.save(update_fields=["starts_at", "ends_at", "calendar_sequence", "calendar_updated_at"])
    _audit(space, actor, "booking.rescheduled", locked, {
        "old_starts_at": old_start.isoformat(), "old_ends_at": old_end.isoformat(),
        "starts_at": starts_at.isoformat(), "ends_at": ends_at.isoformat(),
    })
    from .notifications import notify_booking_status
    notify_booking_status(locked, "confirmed" if locked.status == "confirmed" else "created")
    return _refresh(locked)


@transaction.atomic
def edit_booking_time(booking, *, actor, starts_at, ends_at):
    space, locked = _locked_booking(booking)
    booking_authority.require(actor, space, "manage_reservations")
    require_feature(space, "bookings.staff_tools")
    return move_locked_booking(space, locked, actor=actor, starts_at=starts_at,
                               ends_at=ends_at, now=timezone.now())
