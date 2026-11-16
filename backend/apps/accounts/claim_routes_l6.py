"""Claim policies for release 2 L6's ticketing routes (orders, seats, transfers, passes).

A claim session never buys, claims, transfers or changes a ticket: each of these spends
money or moves an admission between people, so it needs the person's own full sign-in.
The public ticket shop is an anonymous read and ignores a presented claim token.
"""

from apps.accounts.claim_route_types import AnonymousRead, Refused

_REASON = "claim sessions cannot buy, claim, transfer or change tickets"
_ROUTES = (
    ("member-event-order-quote", ("POST",)),
    ("member-event-orders", ("POST",)),
    ("member-orders", ("GET", "HEAD")),
    ("member-order-detail", ("GET", "HEAD")),
    ("member-order-attendees", ("POST",)),
    ("member-order-chase", ("POST",)),
    ("member-order-cancel", ("POST",)),
    ("member-order-seat-claim", ("POST",)),
    ("member-ticket-transfer", ("POST",)),
    ("member-ticket-change-type", ("POST",)),
    ("member-series-passes", ("GET", "HEAD", "POST")),
    ("member-ticket-claim", ("GET", "HEAD", "POST")),
    ("member-ticket-transfer-accept", ("GET", "HEAD", "POST")),
)

L6_CLAIM_ROUTES = {
    **{(name, method): Refused(_REASON) for name, methods in _ROUTES for method in methods},
    **{(name, "OPTIONS"): AnonymousRead() for name, _methods in _ROUTES},
    **{("public-event-ticket-shop", method): AnonymousRead() for method in ("GET", "HEAD", "POST", "OPTIONS")},
}
