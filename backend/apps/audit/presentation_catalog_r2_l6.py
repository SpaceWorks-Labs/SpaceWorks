"""Audit presentation for lane L6: paid ticketing v2 and venue fees (#69, #71, #128 C-20).

Every `event.*` action sits under the dynamic event namespace, which withholds metadata at
read time, so these entries name the action only. Attendee and recipient emails, claim and
transfer tokens and codes are never in an audit row in any case.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P


ENTRIES = (
    P("event.order_created", gettext_noop("Ticket order placed")),
    P("event.pass_order_created", gettext_noop("Series pass ordered")),
    P("event.order_paid", gettext_noop("Ticket order paid")),
    P("event.order_unfulfilled", gettext_noop("Paid order could not be seated")),
    P("event.order_cancelled", gettext_noop("Ticket order cancelled")),
    P("event.order_expired", gettext_noop("Ticket checkout expired")),
    P("event.order_due_opened", gettext_noop("Refund owed on a ticket order")),
    P("event.order_seat_cancelled", gettext_noop("Order seat cancelled")),
    P("event.order_attendees_updated", gettext_noop("Order attendees updated")),
    P("event.seat_invited", gettext_noop("Seat claim invite sent")),
    P("event.seat_claimed", gettext_noop("Seat claimed")),
    P("event.ticket_transfer_offered", gettext_noop("Ticket transfer offered")),
    P("event.ticket_transferred", gettext_noop("Ticket transferred")),
    P("event.ticket_type_changed", gettext_noop("Ticket type changed")),
    P("event.addon_created", gettext_noop("Ticket add-on created")),
    P("event.addon_updated", gettext_noop("Ticket add-on changed")),
    P("event.addon_deleted", gettext_noop("Ticket add-on deleted")),
    P("event.pass_type_saved", gettext_noop("Series pass type saved")),
    P("event.pass_occurrence_cancelled", gettext_noop("Pass occurrence cancelled")),
    P("event.payment_collected_at_desk", gettext_noop("Ticket payment collected at the desk")),
    P("event.refund_policy_overridden", gettext_noop("Event refund policy changed")),
    P("event.sales_settings_updated", gettext_noop("Event sales rules changed")),
    P("event.venue_fee_configured", gettext_noop("Venue fee set")),
    P("event.venue_fee_charged", gettext_noop("Venue fee charged")),
    P("event.booking_decision_linked", gettext_noop("Room booking linked to the event")),
    P("event.booking_decision_replaced", gettext_noop("Linked room booking replaced")),
    P("event.booking_decision_partial_coverage", gettext_noop("Room booking linked with partial time coverage")),
    P("event.created_with_room", gettext_noop("Event created with a room step")),
    P("booking.cancelled_event_room_confirmed", gettext_noop("Booker confirmed cancelling a room that hosts an event")),
    P("event.workshop_machine_linked", gettext_noop("Workshop machine booking linked to the event")),
    P("event.workshop_machine_replaced", gettext_noop("Linked workshop machine booking replaced")),
    P("event.workshop_machine_unlinked", gettext_noop("Workshop machine booking unlinked from the event")),
    P("event.equipment_return_window_changed", gettext_noop("Event equipment return window changed")),
    P("event.equipment_planned", gettext_noop("Equipment planned for event participants")),
    P("event.pay_link_issued", gettext_noop("Ticket pay link issued")),
)
