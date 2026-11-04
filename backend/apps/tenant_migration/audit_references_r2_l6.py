"""Audit metadata IDs written by release-2 lane L6 (paid ticketing v2, venue fees)."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R, S = AuditReferenceDisposition.REMAP, AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT


def _remap(model, *edges):
    return {edge: AuditReference(R, model) for edge in edges}


_ORDER_ACTIONS = ("order_created", "pass_order_created", "order_paid", "order_unfulfilled", "order_cancelled",
                  "order_expired", "order_due_opened", "order_seat_cancelled", "order_attendees_updated",
                  "seat_invited", "seat_claimed", "pass_occurrence_cancelled", "ticket_type_changed")

EDGES = {
    **_remap("events.EventOrder", *((f"event.{action}", "order_id") for action in _ORDER_ACTIONS)),
    **_remap("events.Event", ("event.order_created", "event_id"), ("event.addon_created", "event_id"),
             ("event.addon_deleted", "event_id"), ("event.pass_occurrence_cancelled", "event_id"),
             ("event.venue_fee_configured", "event_id"), ("event.venue_fee_charged", "event_id")),
    **_remap("events.EventSeries", ("event.order_created", "series_id"), ("event.pass_order_created", "series_id"),
             ("event.pass_type_saved", "series_id")),
    **_remap("events.EventOrderSeat", *((f"event.{action}", "seat_id") for action in (
        "order_seat_cancelled", "seat_invited", "seat_claimed"))),
    **_remap("events.EventOrderDue", ("event.order_due_opened", "due_id"), ("event.pass_occurrence_cancelled",
                                                                             "due_id")),
    **_remap("payments.RefundCase", ("event.order_due_opened", "case_id")),
    **_remap("payments.Payment", ("event.order_paid", "payment_id"), ("event.order_unfulfilled", "payment_id"),
             ("event.payment_collected_at_desk", "payment_id"), ("event.venue_fee_charged", "payment_id"),
             ("event.pay_link_issued", "payment_id")),
    **_remap("events.EventRegistration", *((f"event.{action}", "registration_id") for action in (
        "order_created", "order_seat_cancelled", "seat_claimed", "ticket_transfer_offered", "ticket_transferred",
        "ticket_type_changed", "payment_collected_at_desk", "pay_link_issued"))),
    **_remap("events.EventTicketTransfer", ("event.ticket_transfer_offered", "transfer_id"),
             ("event.ticket_transferred", "transfer_id")),
    **_remap("events.EventTicketType", ("event.ticket_type_changed", "from_ticket_type_id"),
             ("event.ticket_type_changed", "ticket_type_id")),
    **_remap("events.EventPromoCode", ("event.order_created", "promo_id")),
    # Accounts are source-local snapshots in audit history, like every other account id there.
    ("event.ticket_transferred", "from_member_id"): AuditReference(S, "accounts.User"),
    ("event.venue_fee_configured", "payer_id"): AuditReference(S, "accounts.User"),
    **_remap("bookings.BookableSpace", ("event.venue_fee_configured", "room_id")),
    # Organizations are deployment-global and never travel: the paying org is source-local provenance.
    ("event.venue_fee_configured", "organization_id"): AuditReference(S, "organizations.Organization"),
}
