"""Analytics views (catalogue version 3): contextual loans and included booking hours.

Release 0.12 (decisions 214, 221b, 221d). A loan context only says WHICH event or booking a
request is lent for; it carries no name, note or contact. Included-hours usage is the
insert-only per-term ledger in minutes, keyed by member id like every other view.
"""

from .types import Col, View


def _context_columns(alias):
    return (
        Col("active", f"{alias}.active", "True while the request is lent for this context."),
        Col("revision", f"{alias}.revision", "Context revision counter."),
        Col("created_at", f"{alias}.created_at", "Created."),
        Col("updated_at", f"{alias}.updated_at", "Last changed."),
    )


VIEWS = (
    View("loan_event_contexts", "events",
         "Borrow requests lent for an event (event equipment, including event-only items).",
         "FROM {events.EventLoanContext} c", "c.makerspace_id", (
             Col("request_id", "c.request_id", "Request (loan_requests)."),
             Col("event_id", "c.event_id", "Event (events); empty once the link is cleared."),
             Col("participant_registration_id", "c.participant_registration_id",
                 "Participant registration (event_registrations), when lent to one participant."),
             *_context_columns("c"),
         ), since=3, requires=("events",)),
    View("loan_booking_contexts", "bookings",
         "Borrow requests lent for a room or machine booking.",
         "FROM {bookings.BookingLoanContext} c", "c.makerspace_id", (
             Col("request_id", "c.request_id", "Request (loan_requests)."),
             Col("booking_id", "c.booking_id", "Booking (bookings); empty once the link is cleared."),
             *_context_columns("c"),
         ), since=3, requires=("bookings",)),
    View("included_hours_usage", "bookings",
         "Insert-only ledger of membership-plan included booking hours: consumed and reversed minutes per term.",
         "FROM {bookings.IncludedHoursUsage} u JOIN {bookings.Booking} b ON b.id = u.booking_id",
         "u.makerspace_id", (
             Col("usage_id", "u.id", "Ledger row id."),
             Col("term_id", "u.term_id", "Membership term (membership_terms)."),
             Col("booking_id", "u.booking_id", "Booking (bookings)."),
             Col("member_id", "b.member_id", "Member who booked (members)."),
             Col("kind", "u.kind", "Room booking or machine time."),
             Col("entry", "u.entry", "Consumed, or reversed after a rejection or cancellation."),
             Col("minutes", "u.minutes", "Included minutes consumed or given back."),
             Col("signed_minutes", "CASE WHEN u.entry = 'consume' THEN u.minutes ELSE -u.minutes END",
                 "Minutes with sign: consumed positive, reversed negative; sum for net usage."),
             Col("generation", "u.generation", "Consumption generation for a restored booking."),
             Col("reverses_id", "u.reverses_id", "The consume row this row undoes."),
             Col("created_at", "u.created_at", "Recorded."),
         ), since=3, requires=("membership", "bookings")),
)
