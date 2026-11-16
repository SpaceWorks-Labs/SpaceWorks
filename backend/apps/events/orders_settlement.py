"""A paid order seats its people (release 2 L6, G27/G28).

Runs after the order's `Payment` settles (online capture, a staff receipt or a waiver,
dispatched post-commit by `payments.admission_settlement`) or at once for a free order.
Under the event write boundary it releases the hold, marks the order paid, turns the
buyer's own seat into the buyer's registration (when the event needs no extra form
answers; otherwise the buyer claims it like any attendee) and emails every other named
seat its claim link.

A paid order that held no seats (`events.seat_holds` off, or its hold lapsed before the
money arrived) is seated only if there is still room. If not it becomes `unfulfilled`
and a staff-approved refund case is opened for the whole amount: money never goes back
on its own, and capacity is never oversold.
"""

import logging

from django.db import transaction
from django.utils import timezone

from apps.audit.services import record

from .models import EventCheckoutHold, EventOrder, EventOrderSeat
from .orders_errors import OrderRefused
from .services_write_boundary import event_write

logger = logging.getLogger(__name__)
SETTLED = ("paid_online", "paid_offline", "waived")


def order_payment(order):
    from apps.payments.models import Payment
    return Payment.objects.filter(makerspace_id=order.makerspace_id, subject_type=Payment.SubjectType.EVENT_ORDER,
                                  subject_id=order.pk).first()


def settle_paid_order(order_id):
    order = EventOrder.objects.select_related("event", "series").filter(pk=order_id).first()
    if order is None or order.status != EventOrder.Status.PENDING:
        return None
    if order.series_id:
        from .passes import settle_pass_order
        return settle_pass_order(order.series, actor=order.buyer, order_id=order.pk)
    return _settle_event(order.event, actor=order.buyer, order_id=order.pk)


@event_write
def _settle_event(event, *, actor, order_id):
    order = EventOrder.objects.select_for_update().filter(pk=order_id, event=event).first()
    return settle_locked(order, actor=actor) if order is not None else None


def _hold_live(order):
    hold = EventCheckoutHold.objects.select_for_update().filter(order=order).first()
    return hold, bool(hold and hold.released_at is None and hold.expires_at > timezone.now())


def release_hold(hold, reason):
    if hold is not None and hold.released_at is None:
        hold.released_at, hold.release_reason = timezone.now(), reason
        hold.save(update_fields=["released_at", "release_reason"])


def _room_for(order):
    from .capacity import registration_spots_left
    from .orders_quote import _require_room
    if order.kind == EventOrder.Kind.PASS:
        lefts = [registration_spots_left(seat.event, None) for seat in order.seats.select_related("event")]
        return all(left is None or left >= 1 for left in lefts)
    rows = [(line.ticket_type, line.quantity, line.unit_amount) for line in order.lines.filter(kind="ticket")]
    try:
        _require_room(order.event, rows)
        return True
    except OrderRefused:
        return False


def settle_locked(order, *, actor):
    order = EventOrder.objects.select_for_update().get(pk=order.pk)
    if order.status != EventOrder.Status.PENDING:
        return order
    payment = order_payment(order)
    if order.total > 0 and (payment is None or payment.status not in SETTLED):
        return order
    hold, live = _hold_live(order)
    release_hold(hold, EventCheckoutHold.Reason.PAID)
    if order.kind == EventOrder.Kind.TYPE_CHANGE:
        from .orders_type_change import settle_type_change
        return settle_type_change(order, actor=actor)
    if not live and order.total > 0 and not _room_for(order):
        return unfulfilled(order, payment, actor=actor)
    order.status, order.paid_at = EventOrder.Status.PAID, timezone.now()
    order.save(update_fields=["status", "paid_at"])
    record(actor, "event.order_paid", makerspace=order.makerspace, target=order,
           meta={"order_id": order.pk, "payment_id": getattr(payment, "pk", None), "total": str(order.total)})
    seat_people(order, actor=actor)
    from .notices_r2_l6 import order_notice
    order_notice(order, "order_confirmed")
    return order


def seat_people(order, *, actor):
    from .orders_attendees import is_buyer_seat, send_invite
    from .orders_claims import fill_seat
    for seat in order.seats.select_related("order__buyer", "line__ticket_type", "event").order_by("pk"):
        if seat.status != EventOrderSeat.Status.UNCLAIMED:
            continue
        if is_buyer_seat(seat):
            try:
                with transaction.atomic():
                    fill_seat(seat, member=order.buyer, actor=actor)
                continue
            except Exception as exc:  # a form or waiver the buyer still has to complete
                logger.info("event_order_buyer_seat_deferred", extra={"seat_id": seat.pk,
                                                                     "failure_type": type(exc).__name__})
        send_invite(seat, actor=actor)


def unfulfilled(order, payment, *, actor):
    from .orders_refunds import open_order_due
    from .models import EventOrderDue
    order.status, order.closed_at = EventOrder.Status.UNFULFILLED, timezone.now()
    order.save(update_fields=["status", "closed_at"])
    order.seats.update(status=EventOrderSeat.Status.VOID, voided_at=timezone.now())
    record(actor, "event.order_unfulfilled", makerspace=order.makerspace, target=order,
           meta={"order_id": order.pk, "payment_id": getattr(payment, "pk", None)})
    if payment is not None and payment.status in ("paid_online", "paid_offline"):
        open_order_due(order, amount=payment.amount, kind=EventOrderDue.Kind.UNFULFILLED, actor=actor,
                       reason_code="order_unfulfilled")
    return order
