"""Release-2 lane L6: paid ticketing v2 and venue fees (#69, #71, #128 C-20, Q-V1).

Every key is a capability under `events`, off by default, and keeps its data when
turned off (#95, #128 C-8). Money owed is still recorded by `charges.events`; these keys
only decide which ticketing tools exist.

* `events.orders` -- one order buys several tickets: tiers, pay-what-you-want, group
  tickets, hidden tickets behind access codes, order limits, the buyer booking fee, one
  registration per attendee and seats claimed by signing in.
* `events.seat_holds` -- a checkout holds its seats for the provider's minimum session
  time, released on expiry or failure.
* `events.addons` -- kit, lunch, T-shirts with variants and session seats, with
  event-local stock (never hardware inventory).
* `events.series_passes` -- one pass for every future occurrence of a series.
* `events.transfers` -- attendees hand a ticket to someone else, and change ticket type.
* `events.desk_collect` -- staff collect a pending ticket payment at the check-in desk.
* `events.refund_override` -- a per-event refund policy that may only get more generous
  after the first sale.
* `events.venue_fees` -- the space charges an outside organiser for hosting (Q-V1 (a)).
"""


def definitions(feature):
    return (
        feature("events.orders", "events", "Ticket orders",
                "Buy several tickets in one order, with tiers, pay-what-you-want, group tickets, hidden "
                "tickets, order limits and a booking fee. Every seat becomes its attendee's own registration.",
                requires_features=("events.ticket_types",)),
        feature("events.seat_holds", "events", "Checkout seat holds",
                "Seats are held while a buyer pays and released when the checkout expires or fails.",
                requires_features=("events.orders",)),
        feature("events.addons", "events", "Ticket add-ons",
                "Kit, lunch, T-shirts with sizes and session seats sold with tickets, with their own stock.",
                requires_features=("events.orders",)),
        feature("events.series_passes", "events", "Series passes",
                "One pass covers every future occurrence of a series.", requires_features=("events.orders",)),
        feature("events.transfers", "events", "Ticket transfers and type changes",
                "Attendees hand their ticket to someone else or switch ticket type when the organiser allows it.",
                requires_features=("events.orders",)),
        feature("events.desk_collect", "events", "Collect payment at the desk",
                "Staff take a pending ticket payment at check-in and record the receipt."),
        feature("events.refund_override", "events", "Per-event refund policy",
                "An event can have its own refund policy; after the first sale it may only become more generous."),
        feature("events.venue_fees", "events", "Venue fees for hosting",
                "Charge an outside organiser for holding their event at the venue, flat or per hour."),
    )
