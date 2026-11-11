"""Explicit tenant projection for retained event/booking decisions."""
from .types import TenantPredicate as P

FIELDS = {"events.EventBookingDecision": "id makerspace event booking creator operation_id generation revision billing_owner intent_version intent created_at updated_at"}
DATASETS = {"events.EventBookingDecision": ("events/booking_decisions.csv", P(("makerspace",), ("event__makerspace", "booking__space__makerspace")))}
# P2-1 workshop machine links: no person, no money, no intent; event and booking are tenant edges.
FIELDS["events.EventMachineBookingLink"] = "id makerspace event booking created_at unlinked_at"
DATASETS["events.EventMachineBookingLink"] = ("events/machine_booking_links.csv", P(("makerspace",), ("event__makerspace", "booking__space__makerspace")))
