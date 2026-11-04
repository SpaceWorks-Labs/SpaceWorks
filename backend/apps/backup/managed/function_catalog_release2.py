"""SQL functions added by release-2 lanes L7 (pairwise judging), L1 (public event surface) and L5 (finance).

L7 guards pairwise comparisons, their invalidations and cursors (events 0060); L1 guards
event short links and their host (events 0061); L5 guards payments and keeps its ledger
rows append-only (payments 0032); L15 freezes booking prices and guards priced payments
(bookings 0021, payments 0033-0034); L23 keeps closed machine sessions final (machines 0032).
"""

RELEASE2_FUNCTIONS = frozenset({
    "events_judgepairwisecomparison_scope_guard",
    "events_judgepairwisecomparison_open_guard",
    "events_judgepairwisecomparison_history_guard",
    "events_judgepairwisecomparison_pii_fence_guard",
    "events_judgepairwiseinvalidation_scope_guard",
    "events_judgepairwiseinvalidation_history_guard",
    "events_judgepairwisecursor_scope_guard",
    "events_short_link_guard",
    "events_short_link_host",
    "payments_payment_l5_guard",
    "payments_l5_append_only",
    # L15: the booking price freeze (bookings 0021) and payment pricing guards (payments 0033-0034).
    "bookings_booking_price_guard",
    "payments_payment_l15_guard",
    "payments_l15_append_only",
    # L23: a closed machine session is final (machines 0032).
    "machines_session_guard",
    # Lane L6: the frozen order quote and append-only order dues.
    "events_order_l6_guard",
    "events_orderdue_l6_guard",
})
