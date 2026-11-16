"""Where each price save calls the price-drop hook, and which items it re-prices (#163A).

One function per kind of save, each called inside that save's transaction after the new
price is written. A change that cannot lower anything (a rise, or a field that is not a
price) still runs the finder, which simply finds nothing -- the frozen quotes decide.

* bookings: the space rate card (`pricing.bookings`), a room's own price or override;
* machines: the space rate card (`pricing.machines`), a machine or material-pool
  override, a machine type's price row -- every prepaid job not yet started is re-quoted;
* events: a ticket type's price, or an event's own price (registrations without a type);
* membership: a plan's price or renewal price.
"""

from apps.payments.price_drop.hook import on_price_change


def after_domain_change(actor, makerspace, domain, target):
    if domain == "bookings":
        from apps.payments.price_drop.find_bookings import find_bookings
        return on_price_change(actor, makerspace, "bookings", target=target, find=lambda: find_bookings(makerspace))
    if domain == "machines":
        return after_machine_price(actor, makerspace, target)
    return []


def after_override(actor, makerspace, target_type, target):
    from apps.payments.models_pricing import PriceOverride
    if target_type == PriceOverride.TargetType.BOOKABLE_SPACE:
        return after_space_price(actor, target)
    if target_type in (PriceOverride.TargetType.MACHINE, PriceOverride.TargetType.CONSUMABLE_POOL):
        return after_machine_price(actor, makerspace, target)
    return []


def after_space_price(actor, space):
    from apps.payments.price_drop.find_bookings import find_bookings
    return on_price_change(actor, space.makerspace, "bookings", target=space,
                           find=lambda: find_bookings(space.makerspace, space_ids=[space.pk]))


def after_machine_price(actor, makerspace, target):
    from apps.payments.price_drop.find_jobs import find_jobs
    return on_price_change(actor, makerspace, "machines", target=target, find=lambda: find_jobs(makerspace))


def after_ticket_price(actor, event, ticket):
    from apps.payments.price_drop.find_tickets import find_tickets
    return on_price_change(actor, event.makerspace, "events", target=ticket,
                           find=lambda: find_tickets(event, ticket_type=ticket))


def after_event_price(actor, event):
    from apps.payments.price_drop.find_tickets import find_tickets
    return on_price_change(actor, event.makerspace, "events", target=event, find=lambda: find_tickets(event))


def after_plan_price(actor, plan):
    from apps.payments.price_drop.find_membership import find_membership
    return on_price_change(actor, plan.makerspace, "membership", target=plan, find=lambda: find_membership(plan))
