"""Audited booking lifecycle transitions behind the stable service barrel."""

from django.db import transaction
from django.utils import timezone

from apps.bookings import notifications
from apps.bookings.exceptions import BookingInvalidTransition
from apps.bookings.models import Booking


def _transition(booking, actor, new_status, action, event, *, require_ended=False, member_cancel=False, reason=""):
    from apps.bookings.services_bookings import _audit, _locked_booking, _refresh

    space, locked = _locked_booking(booking)
    if not member_cancel:
        from .booking_authority import require
        require(actor, space, "manage_reservations")
    cancelling = new_status == Booking.Status.CANCELLED
    allowed = (Booking.Status.PENDING, Booking.Status.CONFIRMED) if cancelling else (Booking.Status.CONFIRMED,)
    if locked.status not in allowed:
        raise BookingInvalidTransition(
            f'Cannot transition booking from {locked.status} to {new_status}.'
        )
    if member_cancel:
        from apps.bookings.services_schedule import member_can_cancel
        from apps.makerspaces.guards import require_module_locked

        locked.space = space
        require_module_locked(space.makerspace, 'bookings')
        if locked.member_id != getattr(actor, 'pk', None):
            raise BookingInvalidTransition('Only the booking member may cancel it.')
        if not member_can_cancel(locked, now=timezone.now()):
            raise BookingInvalidTransition('The booking cancellation cutoff has passed.')
    if require_ended and locked.ends_at > timezone.now():
        raise BookingInvalidTransition('Booking has not ended yet.')
    old_status = locked.status
    fields = ["status", "calendar_sequence", "calendar_updated_at"]
    if cancelling:
        from apps.operations.cancellation_restore import record_cancellation
        fields.extend(record_cancellation(locked, now=timezone.now()))
        locked.decision_reason = reason
        fields.append("decision_reason")
    locked.status = new_status
    locked.calendar_sequence += 1
    locked.calendar_updated_at = timezone.now()
    locked.save(update_fields=fields)
    _audit(
        space,
        actor,
        action,
        locked,
        {
            'booking_id': locked.pk,
            'old_status': old_status,
            'new_status': new_status,
            **({'reason': reason} if cancelling else {}),
        },
    )
    notifications.notify_booking_status(locked, event)
    if cancelling:
        # Decision 221(d): a member may only cancel before the cutoff and staff cancellations are
        # never the member's fault, so a cancelled booking's plan hours always go back.
        from .included_hours_ledger import release
        release(locked, actor)
        from .event_link_notices import booking_changed
        booking_changed(locked, "cancelled")
    return _refresh(locked)


@transaction.atomic
def cancel_booking(booking, *, actor, member_cancel=False, reason="", confirm_event_room=False):
    from .services_decisions import clean_reason
    hosted = None
    if member_cancel:  # decision 223 (m): a booker is told when the room hosts an event, and must confirm
        from .event_host_guard import require_confirmation
        hosted = require_confirmation(booking, actor, confirm_event_room)
    cancelled = _transition(
        booking, actor, Booking.Status.CANCELLED, 'booking.cancelled', 'cancelled',
        member_cancel=member_cancel, reason=clean_reason(reason, required=False),
    )
    from apps.bookings.service_payments import cancel_for_booking

    # Staff cancelling a member's booking owe the full amount (decision 72); a member's
    # own cancellation follows the bookings policy.
    from .event_host_guard import record_confirmed
    record_confirmed(cancelled, actor, hosted)
    by_staff = not member_cancel and getattr(actor, "pk", None) != cancelled.member_id
    cancel_for_booking(cancelled, actor, by_staff=by_staff)
    return cancelled


@transaction.atomic
def complete_booking(booking, *, actor):
    return _transition(
        booking,
        actor,
        Booking.Status.COMPLETED,
        'booking.completed',
        'completed',
        require_ended=True,
    )


@transaction.atomic
def mark_no_show(booking, *, actor):
    return _transition(
        booking,
        actor,
        Booking.Status.NO_SHOW,
        'booking.no_show_marked',
        'no_show',
        require_ended=True,
    )
