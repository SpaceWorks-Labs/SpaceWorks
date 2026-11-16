"""Account-merge dispositions for lane L6 (paid ticketing v2 and venue fees, release 2)."""

from .merge_registry_types import KEEP_ON_SHELL as K, REPOINT as R

_MUTABLE = "Mutable ownership or attribution; moves to the survivor."
_MONEY = ("Who owes or paid an event charge. Stays with the account that bought, exactly like "
          "Payment.member, which validates against it.")
_HISTORY = "Append-only attribution of a staff or member decision; stays with the account that acted."

ROWS = (
    (K, "events.EventOrder", "buyer", _MONEY),
    (K, "events.EventOrderDue", "created_by", _HISTORY),
    (R, "events.EventSalesSettings", "updated_by", _MUTABLE),
    (K, "events.EventTicketTransfer", "from_member accepted_by", _HISTORY),
    (K, "events.EventVenueFee", "payer", _MONEY),
    (R, "events.EventVenueFee", "updated_by", _MUTABLE),
)
