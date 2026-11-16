"""Release-2 lane L6 (paid ticketing v2, venue fees): tenant-dump field snapshot and authority.

Orders, seats, dues, holds, add-ons, pass types, transfers, venue fees and per-event sales
settings travel with their event (data_export `classification_r2_l6`). The frozen order
quote travels unchanged -- ids inside it are source-local history. Claim and transfer
token digests are replaced on the target (`omitted_fields`): a moved space re-sends the
invites. Attendee and recipient emails are the space's own scoped PII and travel.
"""

FIELD_NAMES = {
    "events.EventSalesSettings": "id makerspace event booking_fee_fixed booking_fee_bps max_tickets_per_order "
                                 "transfers_allowed type_changes_allowed transfer_cutoff_hours refund_override "
                                 "full_before_minutes partial_before_minutes partial_percent cancellation_fee "
                                 "policy_text updated_by updated_at",
    "events.EventOrder": "id makerspace event series buyer kind status currency subtotal discount_total fee_total "
                         "total pricing_snapshot digest promo_code source_registration target_ticket_type created_at "
                         "paid_at closed_at reminded_at",
    "events.EventOrderLine": "id order kind ticket_type addon variant pass_type label quantity seats_per_unit "
                             "unit_amount discount_amount line_total",
    "events.EventOrderSeat": "id makerspace order line event status attendee_email claim_token_digest registration "
                             "created_at invited_at reminded_at claimed_at voided_at",
    "events.EventOrderDue": "id makerspace order kind event seat amount refund_case created_by created_at",
    "events.EventCheckoutHold": "id makerspace order event seats expires_at released_at release_reason created_at",
    "events.EventAddon": "id makerspace event name description kind amount stock per_order_limit is_active created_at",
    "events.EventAddonVariant": "id addon label stock is_active",
    "events.EventPassType": "id makerspace series name amount capacity occurrence_refund_amount sales_end_at "
                            "is_active created_at",
    "events.EventTicketTransfer": "id makerspace registration from_member to_email token_digest status accepted_by "
                                  "expires_at created_at decided_at",
    "events.EventVenueFee": "id makerspace event payer organization room mode basis amount status charged_at "
                            "updated_by created_at updated_at",
}
FIELD_NAMES = {label: frozenset(names.split()) for label, names in FIELD_NAMES.items()}
EXTRA_FIELDS = {
    "events.EventTicketType": frozenset("tier_group tier_rank pricing_mode min_amount seats_per_ticket is_hidden "
                                        "min_quantity per_order_limit".split()),
    "events.EventPromoCode": frozenset("kind applies_per ticket_type".split()),
}
PROJECTED_LABELS = frozenset(FIELD_NAMES)


def authority_entries(authority, disposition):
    def same(label, names, chosen, reason):
        return tuple(((label, name), authority(chosen, reason)) for name in names.split())

    keep = disposition.PRESERVE
    return (
        *same("events.EventOrder", "kind status currency subtotal discount_total fee_total total pricing_snapshot "
              "digest created_at paid_at closed_at reminded_at", keep,
              "An order and its frozen quote are the buyer's money history; never recomputed."),
        *same("events.EventOrderLine", "kind label quantity seats_per_unit unit_amount discount_amount line_total",
              keep, "The frozen per-ticket price a buyer paid (L24 reads it)."),
        *same("events.EventOrderSeat", "status attendee_email created_at invited_at reminded_at claimed_at voided_at",
              keep, "A seat and the attendee it is held for are the order's own record."),
        *same("events.EventOrderDue", "kind amount created_at", keep,
              "An append-only amount owed back, decided by staff through its refund case."),
        *same("events.EventCheckoutHold", "seats expires_at released_at release_reason created_at", keep,
              "Hold history; a live hold expires on its own clock."),
        *same("events.EventTicketTransfer", "to_email status expires_at created_at decided_at", keep,
              "A transfer is the record of a ticket changing hands."),
        *same("events.EventVenueFee", "mode basis amount status charged_at created_at updated_at", keep,
              "A hosting fee is the space's own charge configuration."),
    )
