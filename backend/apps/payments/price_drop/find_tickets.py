"""Paid tickets for an event not yet held that would cost less now (#163A).

Per registration, from frozen rows only (lane L6's contract,
`events.orders_pricing.paid_ticket_price`): what the seat really cost after its
discounts and any earlier offer, and the ticket's list price when it was sold -- the
order line's `unit_amount`, or the single registration's quoted line. The drop is taken
in proportion to what the seat cost, so a seat bought with a promo code gets the promo's
share of it. Pay-what-you-want tickets and series passes are never re-priced: the member
chose the amount, or one price covers many occasions.
"""

from decimal import Decimal

from django.utils import timezone

from apps.payments.price_drop.shares import SETTLED, Affected, by_unit

FIXED = "fixed"


def list_price(registration, payment):
    """The ticket's list price at sale, or None for a seat this finder never re-prices."""
    seat = getattr(registration, "order_seat", None)
    if seat is not None:
        return seat.line.unit_amount if seat.line.kind == "ticket" else None
    lines = (payment.pricing_snapshot or {}).get("lines") or []
    if lines and lines[0].get("unit_amount") not in (None, ""):
        return Decimal(str(lines[0]["unit_amount"]))
    from apps.events.service_payments import registration_amount
    return Decimal(registration_amount(registration) or 0)


def find_tickets(event, *, ticket_type=None):
    from apps.events.models import EventRegistration
    from apps.events.orders_pricing import paid_ticket_price

    if event.starts_at is None or event.starts_at <= timezone.now():
        return []
    if ticket_type is not None and ticket_type.pricing_mode != FIXED:
        return []
    after = Decimal(ticket_type.amount if ticket_type is not None else event.payment_amount or 0)
    rows = EventRegistration.objects.filter(event=event, status=EventRegistration.Status.REGISTERED)
    rows = rows.filter(ticket_type=ticket_type) if ticket_type is not None else rows.filter(ticket_type__isnull=True)
    found = []
    for registration in rows.select_related("event").order_by("pk"):
        paid, payment = paid_ticket_price(registration)
        if payment is None or payment.status not in SETTLED:
            continue
        before = list_price(registration, payment)
        if before is None:
            continue
        item = f"registration:{registration.pk}"
        result = by_unit(payment, item, before=before, after=after, paid=paid)
        if result is None:
            continue
        baseline, owed = result
        found.append(Affected(area="events", item_type="registration", item_id=registration.pk, label=event.title,
                              payment=payment, before=baseline, after=after, difference=owed,
                              starts_at=event.starts_at, facts={"registration_id": registration.pk}))
    return found
