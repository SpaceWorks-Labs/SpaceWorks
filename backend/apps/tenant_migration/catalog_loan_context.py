"""Literal portable schema for tenant-owned loan-context associations."""
FIELD_NAMES = {
    "events.EventLoanContext": frozenset("id makerspace request event participant_registration active revision created_at updated_at".split()),
    "bookings.BookingLoanContext": frozenset("id makerspace request booking active revision created_at updated_at".split()),
}
PROJECTED_LABELS = frozenset(FIELD_NAMES)
