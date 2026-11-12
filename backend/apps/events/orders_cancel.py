"""The buyer abandons an unpaid order (release 2 L6, G28): seats back on sale, charge voided.

Only a PENDING order can be abandoned. A paid one is not undone here: its seats are
cancelled one registration at a time, each through the refund policy (`orders_refunds`).
If the charge turns out to be settled already, the order is seated instead.
"""

from django.utils.translation import gettext
from django.utils import timezone

from apps.audit.services import record

from .models import EventCheckoutHold, EventOrder
from .orders_errors import OrderRefused
from .services_write_boundary import event_write


def _cancel_locked(order_id, actor):
    from apps.payments.reconciliation import cancel_pending
    from .orders_settlement import SETTLED, order_payment, release_hold, settle_locked
    order = EventOrder.objects.select_for_update().get(pk=order_id)
    if order.status != EventOrder.Status.PENDING:
        raise OrderRefused("order_not_payable", gettext("Only an unpaid order can be abandoned."))
    payment = order_payment(order)
    if payment is not None and payment.status in SETTLED:
        return settle_locked(order, actor=actor)
    release_hold(EventCheckoutHold.objects.filter(order=order).first(), EventCheckoutHold.Reason.CANCELLED)
    order.status, order.closed_at = EventOrder.Status.CANCELLED, timezone.now()
    order.save(update_fields=["status", "closed_at"])
    if payment is not None:
        cancel_pending(makerspace=order.makerspace, subject_type="event_order", subject_id=order.pk, actor=actor)
    record(actor, "event.order_cancelled", makerspace=order.makerspace, target=order,
           meta={"order_id": order.pk, "reason": "buyer"})
    return order


@event_write
def _cancel_event(event, *, actor, order_id):
    return _cancel_locked(order_id, actor)


@event_write
def _cancel_series(series, *, actor, order_id):
    return _cancel_locked(order_id, actor)


def cancel_pending_order(order, *, actor):
    if order.series_id:
        return _cancel_series(order.series, actor=actor, order_id=order.pk)
    return _cancel_event(order.event, actor=actor, order_id=order.pk)


# Parity C18: an approved refund can also cancel the tickets it paid for.
_LIVE = ("pending_approval", "registered", "waitlisted")


@event_write
def _cancel_seats_for_refund(event, *, actor, order_id):
    """Void every live seat of one ticket order, then cancel the registrations behind them.

    Seats are voided FIRST so the after-commit `orders_refunds.seat_cancelled` hook finds them
    already void and opens no second refund share: the staff-approved amount is the money back.
    Already-void seats and already-cancelled registrations are skipped, so a repeat is a no-op.
    """
    from apps.events import services
    from .models import EventOrderSeat, EventRegistration
    cancelled = []
    seats = (EventOrderSeat.objects.select_for_update(of=("self",))
             .filter(order_id=order_id, order__kind=EventOrder.Kind.TICKETS)
             .exclude(status=EventOrderSeat.Status.VOID).order_by("pk"))
    for seat in seats:
        registration_id = seat.registration_id
        seat.status, seat.voided_at = EventOrderSeat.Status.VOID, timezone.now()
        seat.save(update_fields=["status", "voided_at"])
        record(actor, "event.order_seat_cancelled", makerspace=seat.makerspace, target=seat.order,
               meta={"order_id": order_id, "seat_id": seat.pk, "registration_id": registration_id})
        registration = EventRegistration.objects.filter(pk=registration_id).first() if registration_id else None
        if registration is not None and registration.status in _LIVE:
            services.cancel_registration(registration, actor=None)
            cancelled.append(registration_id)
    return cancelled


@event_write
def _cancel_one_for_refund(registration, *, actor):
    from apps.events import services
    from .models import EventRegistration
    current = EventRegistration.objects.filter(pk=registration.pk).first()
    if current is None or current.status not in _LIVE:
        return []
    services.cancel_registration(current, actor=None)
    return [current.pk]


def cancel_tickets_for_refund(payment, *, actor):
    """The registration ids cancelled by an approved refund on `payment` (none for non-event charges).

    A ticket order cancels every live seat of it; a per-registration charge cancels that registration.
    A series pass is left alone (its occurrences have their own rule). Runs after the approval commits,
    outside the Payment lock, because cancelling takes the event lock.
    """
    from apps.payments.models import Payment
    from .models import EventRegistration
    if payment.subject_type == Payment.SubjectType.EVENT_ORDER:
        order = EventOrder.objects.select_related("event").filter(
            pk=payment.subject_id, makerspace_id=payment.makerspace_id).first()
        if order is None or order.kind != EventOrder.Kind.TICKETS or order.event_id is None:
            return []
        return _cancel_seats_for_refund(order.event, actor=actor, order_id=order.pk)
    if payment.subject_type == Payment.SubjectType.EVENT_REGISTRATION:
        registration = EventRegistration.objects.select_related("event").filter(
            pk=payment.subject_id, event__makerspace_id=payment.makerspace_id).first()
        return _cancel_one_for_refund(registration, actor=actor) if registration is not None else []
    return []
