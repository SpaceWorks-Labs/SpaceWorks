"""Public allowlists shared by H/I definitions and organization strategies."""

COMMUNICATION_GROUPS = (
    "period", "module_key", "channel", "feature", "provider_source", "platform",
    "audience", "skip_reason", "segment_source", "measurement",
)
MESSAGING_STATUS_COUNTS = (
    "pending_count", "sending_count", "accepted_only_count", "sent_only_count",
    "delivered_only_count", "read_count", "failed_count", "skipped_count", "suppressed_count", "held_count", "canceled_count",
)
MESSAGING_COUNTS = (
    "accepted_count", "delivered_count", "read_count", "pending_count", "sending_count",
    "accepted_only_count", "sent_only_count", "delivered_only_count",
    "estimated_segments", "billed_segments", "segments", "abandoned_webhook_count", "held_webhook_count", "held_count", "canceled_count",
    "delivery_rate_numerator", "delivery_rate_denominator", "read_rate_numerator", "read_rate_denominator",
)
COMMUNICATION_COUNTS = (
    "triggered_count", "delivery_count", "attempt_count", "sent_count", "failed_count",
    "skipped_count", "suppressed_count", "bounced_count", "complained_count", "invalid_count",
    "inbox_created_count", "inbox_read_count", "unread_count",
    *MESSAGING_COUNTS,
)
COMMUNICATION_FIELDS = (*COMMUNICATION_GROUPS, *COMMUNICATION_COUNTS,
                        "success_rate_percent", "read_rate_percent", "last_activity_at",
                        "delivery_rate", "read_rate", "consented_member_count")
MOBILE_DEVICE_GROUPS = ("period", "metric", "platform", "environment", "authority", "status")
MOBILE_DEVICE_FIELDS = (*MOBILE_DEVICE_GROUPS, "count")
MOBILE_AUTH_GROUPS = ("period", "metric", "platform", "environment", "outcome", "reason")
MOBILE_AUTH_FIELDS = (*MOBILE_AUTH_GROUPS, "count")
