"""Release-2 lane L6 (paid ticketing v2, venue fees): literal export classification.

Exported with the space: per-event sales settings (booking fee, transfer rules, the
refund override and its buyer-facing text), orders with their lines, seats and dues,
checkout holds, add-ons and variants, series pass types, ticket transfers and venue fees.
Attendee and transfer emails are scoped PII (encrypted at rest, `encryption/registry_r2_l6`).
New columns: the ticket order fields (tiers, pay-what-you-want, group seats, hidden
tickets, order limits) and the promo `kind`, `applies_per` and `ticket_type`.

Omitted, deliberately: a seat's claim token digest and a transfer's token digest --
bearer credential material. A moved space re-sends claim and transfer invites.
"""

from .types import TenantPredicate as P

EXPORTED_FIELDS = {
    "events.EventSalesSettings": "id makerspace event booking_fee_fixed booking_fee_bps max_tickets_per_order "
                                 "transfers_allowed type_changes_allowed transfer_cutoff_hours refund_override "
                                 "full_before_minutes partial_before_minutes partial_percent cancellation_fee "
                                 "policy_text updated_by updated_at",
    "events.EventOrder": "id makerspace event series buyer kind status currency subtotal discount_total fee_total "
                         "total pricing_snapshot digest promo_code source_registration target_ticket_type created_at "
                         "paid_at closed_at reminded_at",
    "events.EventOrderLine": "id order kind ticket_type addon variant pass_type label quantity seats_per_unit "
                             "unit_amount discount_amount line_total",
    "events.EventOrderSeat": "id makerspace order line event status attendee_email "
                             "claim_token_digest registration created_at invited_at reminded_at claimed_at voided_at",
    "events.EventOrderDue": "id makerspace order kind event seat amount refund_case created_by created_at",
    "events.EventCheckoutHold": "id makerspace order event seats expires_at released_at release_reason created_at",
    "events.EventAddon": "id makerspace event name description kind amount stock per_order_limit is_active created_at",
    "events.EventAddonVariant": "id addon label stock is_active",
    "events.EventPassType": "id makerspace series name amount capacity occurrence_refund_amount sales_end_at "
                            "is_active created_at",
    "events.EventTicketTransfer": "id makerspace registration from_member to_email token_digest "
                                  "status accepted_by expires_at created_at decided_at",
    "events.EventVenueFee": "id makerspace event payer organization room mode basis amount status charged_at "
                            "updated_by created_at updated_at",
}
FIELD_ADDITIONS = {
    "events.EventTicketType": "tier_group tier_rank pricing_mode min_amount seats_per_ticket is_hidden min_quantity "
                              "per_order_limit",
    "events.EventPromoCode": "kind applies_per ticket_type",
}
_TOKEN = "Digest of a claim or transfer bearer token; a moved space re-sends the invite."
ALWAYS_OMITTED = {
    ("events.EventOrderSeat", "claim_token_digest"): _TOKEN,
    ("events.EventTicketTransfer", "token_digest"): _TOKEN,
}
NON_CREDENTIAL = {
    ("events.EventOrder", "digest"): "Digest of the quote a buyer was shown (price-changed check); authenticates nothing.",
}
DATASET_SPECS = {
    "events.EventSalesSettings": ("events/sales_settings.csv", P(("makerspace",))),
    "events.EventOrder": ("events/orders.csv", P(("makerspace",))),
    "events.EventOrderLine": ("events/order_lines.csv", P(("order__makerspace",))),
    "events.EventOrderSeat": ("events/order_seats.csv", P(("makerspace",))),
    "events.EventOrderDue": ("events/order_dues.csv", P(("makerspace",))),
    "events.EventCheckoutHold": ("events/checkout_holds.csv", P(("makerspace",))),
    "events.EventAddon": ("events/addons.csv", P(("makerspace",))),
    "events.EventAddonVariant": ("events/addon_variants.csv", P(("addon__makerspace",))),
    "events.EventPassType": ("events/pass_types.csv", P(("makerspace",))),
    "events.EventTicketTransfer": ("events/ticket_transfers.csv", P(("makerspace",))),
    "events.EventVenueFee": ("events/venue_fees.csv", P(("makerspace",))),
}
RELATIONAL_USER_FIELDS = frozenset({
    ("events.EventSalesSettings", "updated_by"),
    ("events.EventOrder", "buyer"),
    ("events.EventOrderDue", "created_by"),
    ("events.EventTicketTransfer", "from_member"),
    ("events.EventTicketTransfer", "accepted_by"),
    ("events.EventVenueFee", "payer"),
    ("events.EventVenueFee", "updated_by"),
})
# The frozen order quote: component and ticket names, prices, promo and ticket ids only.
JSON_FIELDS = frozenset({("events.EventOrder", "pricing_snapshot")})


def extend(fields):
    fields.update(EXPORTED_FIELDS)
    for label, extra in FIELD_ADDITIONS.items():
        fields[label] += " " + extra
    return fields
