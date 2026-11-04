"""Scoped-PII fields added by release-2 lane L6 (ticket orders and transfers)."""


def ticketing_pii_fields(field):
    return (
        field("events.EventOrderSeat", "attendee_email", "makerspace_id", 254, "source", "none"),
        field("events.EventTicketTransfer", "to_email", "makerspace_id", 254, "source", "none"),
    )
