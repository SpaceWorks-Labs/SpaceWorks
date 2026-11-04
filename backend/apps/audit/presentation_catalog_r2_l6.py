"""Audit presentation for lane L6: paid ticketing v2 and venue fees (#69, #71, #128 C-20).

Every `event.*` action sits under the dynamic event namespace, which withholds metadata at
read time, so these entries name the action only. Attendee and recipient emails, claim and
transfer tokens and codes are never in an audit row in any case.
"""

from .presentation_catalog_types import P


ENTRIES = (
    P("event.order_created", "Ticket order placed"),
    P("event.pass_order_created", "Series pass ordered"),
    P("event.order_paid", "Ticket order paid"),
    P("event.order_unfulfilled", "Paid order could not be seated"),
    P("event.order_cancelled", "Ticket order cancelled"),
    P("event.order_expired", "Ticket checkout expired"),
    P("event.order_due_opened", "Refund owed on a ticket order"),
    P("event.order_seat_cancelled", "Order seat cancelled"),
    P("event.order_attendees_updated", "Order attendees updated"),
    P("event.seat_invited", "Seat claim invite sent"),
    P("event.seat_claimed", "Seat claimed"),
    P("event.ticket_transfer_offered", "Ticket transfer offered"),
    P("event.ticket_transferred", "Ticket transferred"),
    P("event.ticket_type_changed", "Ticket type changed"),
    P("event.addon_created", "Ticket add-on created"),
    P("event.addon_updated", "Ticket add-on changed"),
    P("event.addon_deleted", "Ticket add-on deleted"),
    P("event.pass_type_saved", "Series pass type saved"),
    P("event.pass_occurrence_cancelled", "Pass occurrence cancelled"),
    P("event.payment_collected_at_desk", "Ticket payment collected at the desk"),
    P("event.refund_policy_overridden", "Event refund policy changed"),
    P("event.sales_settings_updated", "Event sales rules changed"),
    P("event.venue_fee_configured", "Venue fee set"),
    P("event.venue_fee_charged", "Venue fee charged"),
    P("event.pay_link_issued", "Ticket pay link issued"),
)
