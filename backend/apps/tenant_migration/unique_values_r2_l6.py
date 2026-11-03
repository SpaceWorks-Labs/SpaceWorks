"""Deployment-global uniqueness for lane L6's rows (paid ticketing v2).

One-to-one rows (sales settings, holds, venue fees, seat registrations) follow their
remapped parent. Claim and transfer token digests are bearer material: the target
mints fresh ones and the invites are re-sent.
"""

from .unique_values_policy import FRESH, REMAP, _policy

_FOLLOW = "Unique per remapped parent row; follows the imported parent."
_TOKEN = "Bearer token digests are replaced; the buyer or sender re-sends the invite."

RULES = {
    ("events.EventSalesSettings", "field:event"): _policy(REMAP, _FOLLOW),
    ("events.EventCheckoutHold", "field:order"): _policy(REMAP, _FOLLOW),
    ("events.EventVenueFee", "field:event"): _policy(REMAP, _FOLLOW),
    ("events.EventOrderSeat", "field:registration"): _policy(REMAP, _FOLLOW),
    ("events.EventOrderSeat", "field:claim_token_digest"): _policy(FRESH, _TOKEN),
    ("events.EventTicketTransfer", "field:token_digest"): _policy(FRESH, _TOKEN),
    ("events.EventTicketTransfer", "event_ticket_transfer_one_pending"): _policy(REMAP, _FOLLOW),
    ("events.EventAddonVariant", "event_addon_variant_unique_label"): _policy(REMAP, _FOLLOW),
}
