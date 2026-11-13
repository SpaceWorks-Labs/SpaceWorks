"""What a ticket really cost (release 2 L6): the frozen per-ticket price L24 builds on.

`paid_ticket_price(registration) -> (amount, payment)` is the contract for price-drop
refunds (#163A) and for type changes. It is read from frozen rows only, never from the
ticket type's current price:

* an order seat: its ticket line's net (`line_total`) shared over the line's admissions
  (booking fee excluded); a pass seat: the pass line shared over its occurrences;
* a single registration: its frozen `quoted_amount` (the release-1 flat price for
  legacy rows), charged by its own `event_registration` Payment;
* plus every PAID `type_change` order for that registration, minus every type-change
  difference already owed back, minus every price-drop difference offered (lane L24).

`payment` is the charge a refund for that ticket is opened on (None when nothing was paid).
"""

from decimal import Decimal

from .models import EventOrder, EventOrderDue


def _registration_payment(registration):
    from apps.payments.models import Payment
    return Payment.objects.filter(makerspace_id=registration.event.makerspace_id,
                                  subject_type=Payment.SubjectType.EVENT_REGISTRATION,
                                  subject_id=registration.pk).first()


def _refunded_type_changes(payment, registration):
    total = Decimal("0")
    for case in payment.refund_cases.all():
        for share in (case.policy_snapshot or {}).get("shares", []):
            if share.get("reason_code") == "ticket_type_changed" and share.get("registration_id") == registration.pk:
                total += Decimal(share.get("share") or 0)
    return total


def paid_ticket_price(registration):
    from .orders_refunds import seat_share
    from .orders_settlement import order_payment
    from .service_payments import registration_amount
    seat = getattr(registration, "order_seat", None)
    if seat is not None:
        payment = order_payment(seat.order)
        base = seat_share(seat)
        refunded = sum((due.amount for due in EventOrderDue.objects.filter(
            seat=seat, kind=EventOrderDue.Kind.TYPE_CHANGE)), Decimal("0"))
    else:
        payment = _registration_payment(registration)
        base = Decimal(registration_amount(registration) or 0)
        refunded = _refunded_type_changes(payment, registration) if payment is not None else Decimal("0")
    extra = sum((order.total for order in EventOrder.objects.filter(
        source_registration=registration, kind=EventOrder.Kind.TYPE_CHANGE, status=EventOrder.Status.PAID)),
        Decimal("0"))
    return base + extra - refunded - _price_drop_offered(payment, registration), payment


def _price_drop_offered(payment, registration):
    """Lane L24 (#163A): money already offered back on this seat because its price dropped."""
    if payment is None:
        return Decimal("0")
    from apps.payments.price_drop.shares import prior_shares, standing
    return standing(0, prior_shares(payment, f"registration:{registration.pk}"))[1]
