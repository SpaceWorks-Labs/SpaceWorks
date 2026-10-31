"""Bookings, events and membership lines (lane L15).

* Bookings: `per_booking` (the room's own price, else its override, else the space
  default) plus `per_hour` x the booked time rounded UP to the billing increment, capped
  per started day of the booking.
* Events: the registration price is the event's own (or its ticket type's). The space's
  `per_registration` default only PREFILLS a new event; a published event never follows
  it, so it is not read here.
* Membership: read-through only (lane L4 owns plans, prices and fees). A cheaper tier is
  a cheaper plan (A4).
"""

import math
from decimal import Decimal

from apps.payments.models_pricing import PriceOverride
from apps.payments.pricing.components import component
from apps.payments.pricing.quotes import line

ROOM = PriceOverride.TargetType.BOOKABLE_SPACE


def booking_lines(card, space, *, starts_at=None, ends_at=None):
    target = {"type": ROOM, "id": space.pk, "label": space.name}
    targets = ((ROOM, space.pk),)
    built = []
    flat = card.resolve("per_booking", targets, legacy_item=space.payment_amount)
    if flat.amount > 0:
        built.append(line(component("bookings", "per_booking"), currency=card.currency, quantity=1,
                          unit_amount=flat.amount, rate_source=flat.source, target=target))
    hourly = card.resolve("per_hour", targets)
    if hourly.amount > 0 and starts_at is not None and ends_at is not None and ends_at > starts_at:
        minutes = math.ceil((ends_at - starts_at).total_seconds() / 60)
        increment = hourly.increment if hourly.increment and hourly.increment > 1 else 1
        billed = math.ceil(minutes / increment) * increment
        days = max(1, math.ceil(minutes / 1440))
        cap = hourly.cap * days if hourly.cap is not None else None
        built.append(line(component("bookings", "per_hour"), currency=card.currency,
                          quantity=Decimal(billed) / Decimal(60), unit_amount=hourly.amount,
                          rate_source=hourly.source, cap=cap, target=target,
                          detail={"minutes": minutes, "billed_minutes": billed, "increment": increment,
                                  "cap_per_day": str(hourly.cap) if hourly.cap is not None else None}))
    return built


def event_lines(card, event, *, ticket=None):
    amount = Decimal(ticket.amount if ticket is not None else event.payment_amount or 0)
    if amount <= 0:
        return []
    target = {"type": "event", "id": event.pk, "label": event.title}
    detail = {"ticket_type_id": ticket.pk} if ticket is not None else {}
    return [line(component("events", "per_registration"), currency=card.currency, quantity=1,
                 unit_amount=amount, rate_source="item", target=target, detail=detail)]


def membership_lines(card, plan=None, *, joining=False):
    built = []
    if plan is not None and plan.amount > 0:
        built.append(line(component("membership", "dues"), currency=card.currency, quantity=1,
                          unit_amount=plan.amount, rate_source="item",
                          target={"type": "membership_plan", "id": plan.pk, "label": plan.name}))
    elif plan is None:
        dues = card.default("dues")
        if dues.amount > 0:
            built.append(line(component("membership", "dues"), currency=card.currency, quantity=1,
                              unit_amount=dues.amount, rate_source=dues.source))
    if joining:
        fee = card.default("joining_fee")
        if fee.amount > 0:
            built.append(line(component("membership", "joining_fee"), currency=card.currency, quantity=1,
                              unit_amount=fee.amount, rate_source=fee.source))
    return built
