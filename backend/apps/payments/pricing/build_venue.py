"""Venue-fee lines (lane L6, #128 C-20): what an outside organiser pays to host an event.

Most specific first, per component (`venue_fee` flat, `venue_fee_per_hour`):

1. the event's own venue-fee row: Free is nothing; Custom is its amount, flat or per hour
   by its basis;
2. Inherit: the chosen room's price override, else the space's events rate card.

Hours are the event's length rounded UP to the billing increment (default one minute).
Venue fees are never member-discounted.
"""

import math
from decimal import Decimal

from apps.payments.models_pricing import PriceOverride
from apps.payments.pricing.components import component
from apps.payments.pricing.quotes import line

ROOM = PriceOverride.TargetType.BOOKABLE_SPACE


def _hours(event, increment):
    minutes = max(math.ceil((event.ends_at - event.starts_at).total_seconds() / 60), 0)
    step = increment if increment and increment > 1 else 1
    billed = math.ceil(minutes / step) * step
    return Decimal(billed) / Decimal(60), {"minutes": minutes, "billed_minutes": billed, "increment": step}


def venue_fee_lines(card, event, *, fee):
    target = {"type": "event", "id": event.pk, "label": event.title}
    if fee.mode == "free":
        return []
    if fee.mode == "custom":
        if fee.basis == "per_hour":
            hours, detail = _hours(event, 1)
            return [line(component("events", "venue_fee_per_hour"), currency=card.currency, quantity=hours,
                         unit_amount=fee.amount, rate_source="event", target=target, detail=detail)]
        return [line(component("events", "venue_fee"), currency=card.currency, quantity=1, unit_amount=fee.amount,
                     rate_source="event", target=target)]
    targets = ((ROOM, fee.room_id),) if fee.room_id else ()
    built = []
    flat = card.resolve("venue_fee", targets)
    if flat.amount > 0:
        built.append(line(component("events", "venue_fee"), currency=card.currency, quantity=1,
                          unit_amount=flat.amount, rate_source=flat.source, target=target))
    hourly = card.resolve("venue_fee_per_hour", targets)
    if hourly.amount > 0:
        hours, detail = _hours(event, hourly.increment)
        built.append(line(component("events", "venue_fee_per_hour"), currency=card.currency, quantity=hours,
                          unit_amount=hourly.amount, rate_source=hourly.source, cap=hourly.cap, target=target,
                          detail=detail))
    return built
