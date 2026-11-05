"""The order quote (release 2 L6, G29/G30): what a basket of tickets and add-ons costs.

Order, the same for the preview and the placed order (A8: preview = charge):

1. access codes unlock hidden ticket types; every requested type must be on sale to this
   buyer (tier chain, sales window, audience) -- else `sold_out`;
2. quantities obey the type's `min_quantity` and `per_order_limit`, the event's
   `max_tickets_per_order` (`order_limit`) and capacity, counting group seats (`sold_out`);
3. a fixed ticket costs its price; a pay-what-you-want one costs what the buyer chose, at
   least its minimum (`amount_below_minimum`). Member-only types admit the buyer alone;
4. the member's ONE best automatic discount (L15), then the promo code on top, fixed-price
   tickets only; add-ons at their price with event-local stock;
5. the booking fee (fixed plus basis points of the discounted ticket total) last. Tax is
   frozen on top by L5 when the charge is raised.
"""

from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal

from apps.payments.pricing.components import Component, component
from apps.payments.pricing.quotes import Quote, line

from .orders_errors import OrderRefused

CENT = Decimal("0.01")
PWYW = Component("pay_what_you_want", "Pay what you want", "ticket", "event_order", discountable=False)
ADDON = Component("addon", "Add-on", "item", "event_order", discountable=False)
FEE = Component("booking_fee", "Booking fee", "order", "event_order", discountable=False)
PASS = Component("series_pass", "Series pass", "pass", "event_order", discountable=False)
TYPE_CHANGE = Component("type_change", "Ticket type change", "ticket", "event_order", discountable=False)


@dataclass
class PricedOrder:
    quote: Quote
    tickets: list = field(default_factory=list)  # (ticket, quantity, unit_amount)
    addons: list = field(default_factory=list)   # (addon, variant, quantity)
    promo: object = None
    promo_uses: int = 0
    access_promos: list = field(default_factory=list)
    seats: int = 0


def sales_settings(event):
    from .models import EventSalesSettings
    return EventSalesSettings.objects.filter(event=event).first() or EventSalesSettings(event=event)


def _ticket(event, member, item, unlocked):
    from .models import EventTicketType
    from .ticketing import available_ticket_types
    try:
        pk, quantity = int(item["ticket_type_id"]), int(item.get("quantity") or 0)
    except (KeyError, TypeError, ValueError):
        raise OrderRefused("order_limit", "Each ticket needs a type and a quantity.")
    if not EventTicketType.objects.filter(pk=pk, event=event, purpose="participant").exists():
        raise OrderRefused("sold_out", "That ticket is not on sale.", ticket_type_id=pk)
    ticket = available_ticket_types(event, member, unlocked=unlocked).filter(pk=pk).first()
    if ticket is None:
        raise OrderRefused("sold_out", "That ticket is not on sale.", ticket_type_id=pk)
    if quantity < ticket.min_quantity or (ticket.per_order_limit and quantity > ticket.per_order_limit):
        raise OrderRefused("order_limit", "That quantity is not allowed for this ticket.", ticket_type_id=pk)
    if ticket.audience == "member" and quantity * ticket.seats_per_ticket > 1:
        raise OrderRefused("order_limit", "A member ticket admits the buyer only.", ticket_type_id=pk)
    unit = Decimal(ticket.amount)
    if ticket.pricing_mode == "pwyw":
        try:
            unit = Decimal(str(item.get("amount", ticket.amount))).quantize(CENT, rounding=ROUND_HALF_UP)
        except (ArithmeticError, TypeError, ValueError):
            raise OrderRefused("amount_below_minimum", "Enter the amount you want to pay.", ticket_type_id=pk)
        if unit < ticket.min_amount:
            raise OrderRefused("amount_below_minimum", f"The minimum for this ticket is {ticket.min_amount}.",
                               ticket_type_id=pk, minimum=str(ticket.min_amount))
    return ticket, quantity, unit


def _require_room(event, tickets):
    from .capacity import registration_spots_left
    seats = 0
    for ticket, quantity, _unit in tickets:
        wanted = quantity * ticket.seats_per_ticket
        seats += wanted
        left = registration_spots_left(event, ticket)
        if left is not None and wanted > left:
            raise OrderRefused("sold_out", "Not enough places are left for this ticket.",
                               ticket_type_id=ticket.pk, spots_left=left)
    left = registration_spots_left(event, None)
    if left is not None and seats > left:
        raise OrderRefused("sold_out", "Not enough places are left at this event.", spots_left=left)
    return seats


def _addons(event, items):
    from .addons import require_available
    from .feature_gates import require_feature
    from .models import EventAddon, EventAddonVariant
    if not items:
        return []
    require_feature(event, "events.addons")
    rows = []
    for item in items:
        addon = EventAddon.objects.filter(pk=item.get("addon_id"), event=event).first()
        variant = (EventAddonVariant.objects.filter(pk=item.get("variant_id"), addon=addon).first()
                   if item.get("variant_id") and addon else None)
        quantity = int(item.get("quantity") or 0)
        if addon is None or quantity < 1 or (item.get("variant_id") and variant is None):
            raise OrderRefused("addon_unavailable", "That add-on is not available.")
        require_available(addon, variant, quantity)
        rows.append((addon, variant, quantity))
    return rows


def build_quote(event, member, request, *, lock=False, addons_only=False):
    from apps.payments.pricing import best_discount
    from apps.payments.pricing.rates import RateCard
    from .feature_gates import require_feature
    from .orders_codes import apply_promo, discount_promo, unlocked_types
    require_feature(event, "events.orders")
    unlocked, access = unlocked_types(event, request.get("access_codes"), lock=lock)
    items = [] if addons_only else request.get("tickets") or []
    if not items and not addons_only:
        raise OrderRefused("order_limit", "Choose at least one ticket.")
    tickets = [_ticket(event, member, item, unlocked) for item in items]
    settings_row = sales_settings(event)
    if sum(quantity for _ticket_row, quantity, _unit in tickets) > settings_row.max_tickets_per_order:
        raise OrderRefused("order_limit", f"At most {settings_row.max_tickets_per_order} tickets per order.",
                           limit=settings_row.max_tickets_per_order)
    seats = _require_room(event, tickets) if tickets else 0
    addons = _addons(event, request.get("addons"))
    currency = RateCard(event.makerspace, "events").currency
    target = {"type": "event", "id": event.pk, "label": event.title}
    lines = [line(PWYW if ticket.pricing_mode == "pwyw" else component("events", "per_registration"),
                  currency=currency, quantity=quantity, unit_amount=unit, rate_source="item", target=target,
                  detail={"ticket_type_id": ticket.pk, "seats_per_ticket": ticket.seats_per_ticket,
                          "label": ticket.name})
             for ticket, quantity, unit in tickets]
    lines += [line(ADDON, currency=currency, quantity=quantity, unit_amount=addon.amount, rate_source="item",
                   target=target, detail={"addon_id": addon.pk, "variant_id": getattr(variant, "pk", None),
                                          "label": f"{addon.name} ({variant.label})" if variant else addon.name})
              for addon, variant, quantity in addons]
    priced = Quote(domain="events", currency=currency, lines=tuple(lines), mode="paid")
    priced = best_discount(event.makerspace, "events", member, priced) if member is not None else priced
    promo = discount_promo(event, request.get("promo_code"), lock=lock)
    discounts, uses = apply_promo(promo, [(index, ticket, quantity, priced.lines[index].net)
                                          for index, (ticket, quantity, _unit) in enumerate(tickets)
                                          if ticket.pricing_mode == "fixed"])
    lines = [replace(row, discount=row.discount + discounts.get(index, Decimal("0")))
             for index, row in enumerate(priced.lines)]
    ticket_net = sum((row.net for row in lines[:len(tickets)]), Decimal("0"))
    fee = (Decimal(settings_row.booking_fee_fixed) + ticket_net * Decimal(settings_row.booking_fee_bps) / 10000
           if ticket_net > 0 else Decimal("0"))
    if fee > 0:
        lines.append(line(FEE, currency=currency, quantity=1, unit_amount=fee.quantize(CENT, rounding=ROUND_HALF_UP),
                          rate_source="event", target=target))
    saving = sum(discounts.values(), Decimal("0"))
    priced = replace(priced, lines=tuple(lines),
                     promo={"id": promo.pk, "saving": str(saving)} if promo is not None and saving > 0 else None)
    return PricedOrder(quote=priced, tickets=tickets, addons=addons, promo=promo if uses else None,
                       promo_uses=uses, access_promos=access, seats=seats)
