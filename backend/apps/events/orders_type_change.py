"""Ticket-type change (release 2 L6, G32), when the organiser allows it.

The new type must be on sale to the holder with a place left. The difference is worked
out against what the holder actually paid (`orders_pricing.paid_ticket_price`):

* dearer: a new order of kind `type_change` for the difference, with its own checkout;
  the switch happens when it is paid (and only if the new type still has room);
* cheaper: the switch happens now and the difference opens a staff-approved refund case
  on the original charge (never money on its own);
* the same price: the switch happens now.
"""

from django.utils.translation import gettext
from decimal import Decimal

from django.utils import timezone

from apps.audit.services import record

from .models import EventOrder, EventOrderDue, EventOrderLine, EventRegistration
from .orders_errors import OrderRefused
from .services_write_boundary import event_write


def new_price(event, member, ticket):
    from .service_payments import member_price
    price, _saving = member_price(event, member, Decimal(ticket.amount), ticket)
    return Decimal(price)


def _target(event, member, ticket_type_id, current):
    from .capacity import registration_spots_left
    from .ticketing import available_ticket_types
    ticket = available_ticket_types(event, member).filter(pk=ticket_type_id).exclude(pk=current).first()
    if ticket is None or ticket.pricing_mode != "fixed" or ticket.seats_per_ticket != 1:
        raise OrderRefused("type_change_not_allowed", gettext("That ticket type is not available to change to."))
    left = registration_spots_left(event, ticket)
    if left is not None and left < 1:
        raise OrderRefused("sold_out", gettext("That ticket type has sold out."))
    return ticket


@event_write
def change_type(registration, *, actor, ticket_type_id, digest=None):
    from apps.payments.pricing import verify_digest
    from apps.payments.pricing.quotes import Quote, line
    from apps.payments.pricing.rates import RateCard
    from .orders_checkout import _payment, _schedule_checkout
    from .orders_pricing import paid_ticket_price
    from .orders_quote import TYPE_CHANGE
    from .transfers import require_transfers
    row = EventRegistration.objects.select_for_update().select_related("event__makerspace").get(pk=registration.pk)
    if row.member_id != actor.pk:
        raise OrderRefused("type_change_not_allowed", gettext("Only the ticket holder can change it."))
    require_transfers(row, flag="type_changes_allowed")
    event = row.event
    ticket = _target(event, actor, ticket_type_id, row.ticket_type_id)
    paid, payment = paid_ticket_price(row)
    difference = new_price(event, actor, ticket) - paid
    from apps.payments.availability import charge_tracking_enabled
    if difference > 0 and not charge_tracking_enabled(event.makerspace, "events"):
        # #184: with event charges off a dearer type costs nothing more, so the switch is
        # immediate; a cheaper switch still refunds money that was really collected.
        difference = Decimal("0")
    currency = RateCard(event.makerspace, "events").currency
    item = line(TYPE_CHANGE, currency=currency, quantity=1, unit_amount=max(difference, Decimal("0")),
                rate_source="item", target={"type": "event", "id": event.pk, "label": event.title},
                detail={"from_ticket_type_id": row.ticket_type_id, "ticket_type_id": ticket.pk,
                        "difference": str(difference)})
    quote = verify_digest(Quote(domain="events", currency=currency, lines=(item,), mode="paid"), digest)
    if difference > 0:
        order = EventOrder.objects.create(
            makerspace=event.makerspace, event=event, buyer=actor, kind=EventOrder.Kind.TYPE_CHANGE,
            currency=currency, subtotal=quote.subtotal, total=quote.total, digest=quote.digest,
            pricing_snapshot=quote.to_snapshot(), source_registration=row, target_ticket_type=ticket)
        EventOrderLine.objects.create(order=order, kind=EventOrderLine.Kind.TYPE_CHANGE, ticket_type=ticket,
                                      label=f"Change to {ticket.name}", quantity=1, unit_amount=difference,
                                      line_total=difference)
        record(actor, "event.order_created", makerspace=event.makerspace, target=order,
               meta={"order_id": order.pk, "kind": "type_change", "registration_id": row.pk,
                     "total": str(order.total)})
        payment = _payment(order, actor)
        _schedule_checkout(payment)
        return {"status": "payment_required", "order": order, "payment": payment, "registration": row}
    switch(row, ticket, actor=actor)
    if difference < 0 and payment is not None:
        refund_difference(row, payment, -difference, actor=actor)
    return {"status": "changed", "order": None, "payment": None, "registration": row}


def switch(row, ticket, *, actor, order=None):
    from .services_calendar import calendar_registration_changed
    old = row.ticket_type_id
    row.ticket_type, row.version = ticket, row.version + 1
    row.save(update_fields=["ticket_type", "version"])
    calendar_registration_changed(row)
    record(actor, "event.ticket_type_changed", makerspace=row.event.makerspace, target=row,
           meta={"registration_id": row.pk, "from_ticket_type_id": old, "ticket_type_id": ticket.pk,
                 "order_id": getattr(order, "pk", None)})


def refund_difference(row, payment, amount, *, actor):
    from apps.payments.services_refund_partial import add_due_share
    from .orders_refunds import open_order_due
    seat = getattr(row, "order_seat", None)
    if seat is not None and payment.subject_type == "event_order":
        return open_order_due(seat.order, amount=amount, kind=EventOrderDue.Kind.TYPE_CHANGE, actor=actor,
                              reason_code="ticket_type_changed", seat=seat)
    return add_due_share(payment, amount=amount, reason_code="ticket_type_changed", actor=actor,
                         snapshot={"registration_id": row.pk})


def settle_type_change(order, *, actor):
    """A paid type-change order switches the ticket, or is unfulfilled if the type filled up."""
    from .capacity import registration_spots_left
    from .orders_settlement import order_payment, unfulfilled
    row = EventRegistration.objects.select_for_update().filter(pk=order.source_registration_id).first()
    ticket = order.target_ticket_type
    left = registration_spots_left(order.event, ticket) if ticket else 0
    if row is None or row.status != EventRegistration.Status.REGISTERED or (left is not None and left < 1):
        return unfulfilled(order, order_payment(order), actor=actor)
    order.status, order.paid_at = EventOrder.Status.PAID, timezone.now()
    order.save(update_fields=["status", "paid_at"])
    switch(row, ticket, actor=actor, order=order)
    from .notices_r2_l6 import order_notice
    order_notice(order, "ticket_type_changed")
    return order
