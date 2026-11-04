"""SQL functions added by release-2 lanes L7 (pairwise judging), L1 (public event surface) and L5 (finance).

L7 guards pairwise comparisons, their invalidations and cursors (events 0060); L1 guards
event short links and their host (events 0061); L5 guards payments and keeps its ledger
rows append-only (payments 0032).
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
    # Lane L6: the frozen order quote and append-only order dues.
    "events_order_l6_guard",
    "events_orderdue_l6_guard",
    # Lane L22: the frozen shop order quote, append-only stock movements and returns, frozen cash-ups.
    "shop_order_l22_guard",
    "shop_stockmovement_l22_guard",
    "shop_orderreturn_l22_guard",
    "shop_cashsession_l22_guard",
})
