"""Literal portable snapshot for the retained venue decision."""
FIELD_NAMES = {"events.EventBookingDecision": frozenset("id makerspace event booking creator operation_id generation revision billing_owner intent_version intent created_at updated_at".split())}
# P2-1 workshop machine links travel beside the decision (plain FK remap, no intent or creator).
FIELD_NAMES["events.EventMachineBookingLink"] = frozenset("id makerspace event booking created_at unlinked_at".split())
PROJECTED_LABELS = frozenset(FIELD_NAMES)

JSON_FIELDS = frozenset({("events.EventBookingDecision", "intent")})
