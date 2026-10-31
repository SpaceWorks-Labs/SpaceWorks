"""Exact, zero-money cancellation undo under resource → booking locks."""

from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone
from apps.accounts.account_obligations import lock_obligation_owner

from apps.makerspaces import limits
from apps.operations.cancellation_restore import require_exact_restore, require_restorable
from apps.payments.availability import charge_tracking_enabled
from apps.payments.models import Payment

from . import booking_authority
from .admission import admission_status, require_feature, validate_admission
from .exceptions import BookingInvalidTransition
from .models import Booking
from .services_bookings import _audit, _locked_booking, _refresh

RESTORABLE = (Booking.Status.PENDING, Booking.Status.CONFIRMED)


def annotate_restore_history(queryset):
    return queryset.annotate(restore_has_charge=Exists(Payment.objects.filter(
        makerspace_id=OuterRef("space__makerspace_id"),
        subject_type=Payment.SubjectType.BOOKING, subject_id=OuterRef("pk"),
    )))


@transaction.atomic
def _priced(booking):
    # Lane L15: the booking's price comes from the pricing kernel (per booking + per hour).
    from .service_payments import booking_quote
    return booking_quote(booking).total > 0


def restore_booking(booking, *, actor):
    space, locked = _locked_booking(booking)
    locked.member = lock_obligation_owner(locked.member)
    booking_authority.require(actor, space, "manage_reservations")
    require_feature(space, "bookings.staff_tools")
    now = timezone.now()
    locked._arrival_clock = now
    admitted = admission_status(space)
    previous = require_restorable(
        locked, now=now, cancelled_status=Booking.Status.CANCELLED, allowed_statuses=RESTORABLE,
        has_charge=Payment.objects.filter(
            makerspace_id=space.makerspace_id, subject_type=Payment.SubjectType.BOOKING,
            subject_id=locked.pk,
        ).exists(),
        would_charge=bool(admitted == Booking.Status.CONFIRMED
                          and locked.member_id and _priced(locked)
                          and charge_tracking_enabled(space.makerspace, "bookings")),
    )
    if locked.member_id is None:
        raise BookingInvalidTransition("An active booking owner is required to restore a reservation.")
    require_exact_restore(previous, admitted)
    locked.status = admitted
    validate_admission(space, locked, now=now, actor=actor)
    limits.check_quota(space.makerspace, "bookings", adding=1)
    locked.cancelled_at = None
    locked.status_before_cancel = ""
    # The cancellation reason stays in the audit history; the live booking no longer has one.
    locked.decision_reason = ""
    locked.calendar_sequence += 1
    locked.calendar_updated_at = now
    locked.save(update_fields=["status", "cancelled_at", "status_before_cancel", "decision_reason",
                               "calendar_sequence", "calendar_updated_at"])
    _audit(space, actor, "booking.restored", locked, {"booking_id": locked.pk, "status": admitted})
    from .notifications import notify_booking_status
    notify_booking_status(locked, "restored")
    return _refresh(locked)
