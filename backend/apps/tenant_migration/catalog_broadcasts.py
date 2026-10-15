"""Literal communication-history fields and inert target projection."""

FIELD_NAMES = {
    "bookings.BookingBroadcast": frozenset("id makerspace space created_by subject body status created_at updated_at queued_at completed_at recipient_cursor recipients_complete statuses window_start window_end".split()),
    "bookings.BookingBroadcastDelivery": frozenset("id campaign recipient outbox status created_at updated_at".split()),
    "events.EventBroadcast": frozenset("id makerspace event created_by subject body status created_at updated_at queued_at completed_at recipient_cursor recipients_complete statuses attendance".split()),
    "events.EventBroadcastDelivery": frozenset("id campaign recipient outbox status created_at updated_at".split()),
}
EXPORTED_FIELDS = {label: " ".join(sorted(names)) for label, names in FIELD_NAMES.items()}
REASON = "Campaign history travels, but target import can never reconstruct sendable authority."


def authority_entries(authority, disposition):
    return tuple((edge, authority((disposition.PRESERVE, disposition.RESET), REASON)) for edge in (
        ("bookings.BookingBroadcast", "status"), ("bookings.BookingBroadcast", "recipient_cursor"),
        ("bookings.BookingBroadcast", "recipients_complete"), ("bookings.BookingBroadcastDelivery", "outbox"),
        ("bookings.BookingBroadcastDelivery", "status"),
        ("events.EventBroadcast", "status"), ("events.EventBroadcast", "recipient_cursor"),
        ("events.EventBroadcast", "recipients_complete"), ("events.EventBroadcastDelivery", "outbox"),
        ("events.EventBroadcastDelivery", "status"),
    ))


def projections(field):
    return {
        ("bookings.BookingBroadcast", "status"): field("cancelled", condition=("status", frozenset({"draft", "queued", "sending"})), reason=REASON),
        ("bookings.BookingBroadcast", "recipient_cursor"): field(0, reason=REASON),
        ("bookings.BookingBroadcast", "recipients_complete"): field(True, reason=REASON),
        ("bookings.BookingBroadcastDelivery", "outbox"): field(None, reason=REASON),
        ("bookings.BookingBroadcastDelivery", "status"): field("skipped", condition=("status", "pending"), reason=REASON),
        ("events.EventBroadcast", "status"): field("cancelled", condition=("status", frozenset({"draft", "queued", "sending"})), reason=REASON),
        ("events.EventBroadcast", "recipient_cursor"): field(0, reason=REASON),
        ("events.EventBroadcast", "recipients_complete"): field(True, reason=REASON),
        ("events.EventBroadcastDelivery", "outbox"): field(None, reason=REASON),
        ("events.EventBroadcastDelivery", "status"): field("skipped", condition=("status", "pending"), reason=REASON),
    }
