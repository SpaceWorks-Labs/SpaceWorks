"""Literal portable snapshot for the retained venue decision."""
FIELD_NAMES = {"events.EventBookingDecision": frozenset("id makerspace event booking creator operation_id generation revision billing_owner intent_version intent created_at updated_at".split())}
# P2-1 workshop machine links travel beside the decision (plain FK remap, no intent or creator).
FIELD_NAMES["events.EventMachineBookingLink"] = frozenset("id makerspace event booking created_at unlinked_at".split())
PROJECTED_LABELS = frozenset(FIELD_NAMES)

JSON_FIELDS = frozenset({("events.EventBookingDecision", "intent")})
# Decision 342 machine use logged with an event (plain FK remap; the approval's amount is the organiser's record).
FIELD_NAMES["events.MachineEventLink"] = frozenset(
    "id makerspace event machine_type session service_request booking source created_at".split())
FIELD_NAMES["events.MachineEventCostApproval"] = frozenset(
    "id makerspace link decision amount currency payment note created_at".split())
PROJECTED_LABELS = frozenset(FIELD_NAMES)
