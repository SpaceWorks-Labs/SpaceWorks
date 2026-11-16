"""Literal tenant-export declarations for independently owned loan contexts."""
from .types import TenantPredicate as P

FIELDS = {
    "events.EventLoanContext": "id makerspace request event participant_registration active revision created_at updated_at",
    "bookings.BookingLoanContext": "id makerspace request booking active revision created_at updated_at",
}
DATASETS = {
    "events.EventLoanContext": ("events/loan_contexts.csv", P(("makerspace",), ("request__makerspace", "event__makerspace", "participant_registration__event__makerspace"))),
    "bookings.BookingLoanContext": ("bookings/loan_contexts.csv", P(("makerspace",), ("request__makerspace", "booking__space__makerspace"))),
}
# Per-module concurrency epochs (opaque version strings); no ids, and the target
# creates fresh generations on import.
NON_REFERENCE_JSON_FIELDS = frozenset({("makerspaces.Makerspace", "loan_context_generations")})
