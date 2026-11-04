"""Phase 2 bookings scoped-PII fields: the free-text departure remark."""


def booking_departure_pii_fields(field_type):
    return (field_type("bookings.BookingDepartureEvent", "remark", "makerspace_id", None, "source", "none"),)
