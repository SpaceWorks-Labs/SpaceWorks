"""Explicit tenant projection for retained event/booking decisions."""
from .types import TenantPredicate as P

FIELDS = {"events.EventBookingDecision": "id makerspace event booking creator operation_id generation revision billing_owner intent_version intent created_at updated_at"}
DATASETS = {"events.EventBookingDecision": ("events/booking_decisions.csv", P(("makerspace",), ("event__makerspace", "booking__space__makerspace")))}
# P2-1 workshop machine links: no person, no money, no intent; event and booking are tenant edges.
FIELDS["events.EventMachineBookingLink"] = "id makerspace event booking created_at unlinked_at"
DATASETS["events.EventMachineBookingLink"] = ("events/machine_booking_links.csv", P(("makerspace",), ("event__makerspace", "booking__space__makerspace")))
# Decision 342 machine use logged with an event: no person (the member is the session's or request's own), no secret.
# The cost approval keeps the charge amount it saw and the Payment edge; it never owns money.
FIELDS["events.MachineEventLink"] = "id makerspace event machine_type session service_request booking source created_at"
DATASETS["events.MachineEventLink"] = ("events/machine_event_links.csv", P(
    ("makerspace",), ("event__makerspace", "session__makerspace", "service_request__makerspace", "booking__space__makerspace")))
FIELDS["events.MachineEventCostApproval"] = "id makerspace link decision amount currency payment note created_at"
DATASETS["events.MachineEventCostApproval"] = ("events/machine_event_cost_approvals.csv", P(
    ("makerspace",), ("link__makerspace", "payment__makerspace")))
