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
    View("machine_event_links", "events",
         "Machine sessions and service requests logged as done for an event (decision 342), with the organiser's "
         "latest decision on charging the cost to the event. No person or note: join sessions or service requests.",
         "FROM {events.MachineEventLink} l LEFT JOIN (SELECT DISTINCT ON (link_id) link_id, decision, amount, currency "
         "FROM {events.MachineEventCostApproval} ORDER BY link_id, created_at DESC, id DESC) d ON d.link_id = l.id",
         "l.makerspace_id", (
             Col("link_id", "l.id", "Link id."),
             Col("event_id", "l.event_id", "Event (events)."),
             Col("machine_type_id", "l.machine_type_id", "Machine type (machine_types)."),
             Col("session_id", "l.session_id", "Machine session, when the link is on a session."),
             Col("service_request_id", "l.service_request_id", "Service request, when the link is on a job."),
             Col("booking_id", "l.booking_id", "Machine-time booking (bookings), when the link is on a booking."),
             Col("source", "l.source", "Who gave the link: requester, adapter or manager."),
             Col("cost_decision", "d.decision", "Latest organiser decision: approved or withdrawn; empty if none."),
             Col("cost_amount", "d.amount", "The charge as it stood when the organiser decided."),
             Col("cost_currency", "d.currency", "Currency of that charge."),
             Col("created_at", "l.created_at", "Linked."),
         ), since=3, requires=("events",)),
    View("loan_booking_contexts", "bookings",
         "Borrow requests lent for a room or machine booking.",
         "FROM {bookings.BookingLoanContext} c", "c.makerspace_id", (
             Col("request_id", "c.request_id", "Request (loan_requests)."),
             Col("booking_id", "c.booking_id", "Booking (bookings); empty once the link is cleared."),
             *_context_columns("c"),
         ), since=3, requires=("bookings",)),
    View("loan_charges", "inventory",
         "Money raised for a borrow request (deposit, late fee, rental, damage, lost item) with its state and "
         "the count of effective offline settlements, read as stored in the payments ledger.",
         "FROM {payments.Payment} p "
         "LEFT JOIN {hardware_requests.RequesterAccountability} a "
         "ON a.id = p.subject_id AND p.subject_type IN ('loan_damage', 'loan_lost') "
         "LEFT JOIN (SELECT m.payment_id, count(*) AS n FROM {payments.ManualSettlement} m "
         "WHERE NOT EXISTS (SELECT 1 FROM {payments.ManualSettlement} m2 WHERE m2.amends_id = m.id) "
         "GROUP BY m.payment_id) s ON s.payment_id = p.id "
         "WHERE p.subject_type IN ('loan_deposit', 'loan_late_fee', 'loan_rental', 'loan_damage', 'loan_lost')",
         "p.makerspace_id", (
             Col("payment_id", "p.id", "Charge id (payments)."),
             Col("request_id", "CASE WHEN p.subject_type IN ('loan_damage', 'loan_lost') THEN a.request_id "
                 "ELSE p.subject_id END", "Request (loan_requests) the charge belongs to."),
             Col("subject_type", "p.subject_type", "Deposit, late fee, rental, damage or lost item."),
             Col("amount", "p.amount", "Amount."),
             Col("currency", "p.currency", "Currency."),
             Col("status", "p.status", "Charge state: pending, paid online or offline, waived or canceled."),
             Col("settlements", "coalesce(s.n, 0)", "Effective offline settlements recorded against the charge."),
             Col("created_at", "p.created_at", "Raised."),
         ), since=3),
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
