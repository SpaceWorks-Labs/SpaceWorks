"""Audit presentation for lane L6: paid ticketing v2 and venue fees (#69, #71, #128 C-20).

Every `event.*` action sits under the dynamic event namespace, which withholds metadata at
read time, so these entries name the action only. Attendee and recipient emails, claim and
transfer tokens and codes are never in an audit row in any case.
"""

from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P


ENTRIES = (
    P("event.order_created", gettext_lazy("Ticket order placed")),
    P("event.pass_order_created", gettext_lazy("Series pass ordered")),
    P("event.order_paid", gettext_lazy("Ticket order paid")),
    P("event.order_unfulfilled", gettext_lazy("Paid order could not be seated")),
    P("event.order_cancelled", gettext_lazy("Ticket order cancelled")),
    P("event.order_expired", gettext_lazy("Ticket checkout expired")),
    P("event.order_due_opened", gettext_lazy("Refund owed on a ticket order")),
    P("event.order_seat_cancelled", gettext_lazy("Order seat cancelled")),
    P("event.order_attendees_updated", gettext_lazy("Order attendees updated")),
    P("event.seat_invited", gettext_lazy("Seat claim invite sent")),
    P("event.seat_claimed", gettext_lazy("Seat claimed")),
    P("event.ticket_transfer_offered", gettext_lazy("Ticket transfer offered")),
    P("event.ticket_transferred", gettext_lazy("Ticket transferred")),
    P("event.ticket_type_changed", gettext_lazy("Ticket type changed")),
    P("event.addon_created", gettext_lazy("Ticket add-on created")),
    P("event.addon_updated", gettext_lazy("Ticket add-on changed")),
    P("event.addon_deleted", gettext_lazy("Ticket add-on deleted")),
    P("event.pass_type_saved", gettext_lazy("Series pass type saved")),
    P("event.pass_occurrence_cancelled", gettext_lazy("Pass occurrence cancelled")),
    P("event.payment_collected_at_desk", gettext_lazy("Ticket payment collected at the desk")),
    P("event.refund_policy_overridden", gettext_lazy("Event refund policy changed")),
    P("event.sales_settings_updated", gettext_lazy("Event sales rules changed")),
    P("event.venue_fee_configured", gettext_lazy("Venue fee set")),
    P("event.venue_fee_charged", gettext_lazy("Venue fee charged")),
    P("event.pay_link_issued", gettext_lazy("Ticket pay link issued")),
)
