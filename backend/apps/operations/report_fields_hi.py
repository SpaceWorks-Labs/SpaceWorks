"""Public allowlists shared by H/I definitions and organization strategies."""

COMMUNICATION_GROUPS = (
    "period", "module_key", "channel", "feature", "provider_source", "platform",
)
COMMUNICATION_COUNTS = (
    "triggered_count", "delivery_count", "attempt_count", "sent_count", "failed_count",
    "skipped_count", "suppressed_count", "bounced_count", "complained_count", "invalid_count",
    "inbox_created_count", "inbox_read_count", "unread_count",
)
COMMUNICATION_FIELDS = (*COMMUNICATION_GROUPS, *COMMUNICATION_COUNTS,
                        "success_rate_percent", "read_rate_percent", "last_activity_at")
MOBILE_DEVICE_GROUPS = ("period", "metric", "platform", "environment", "authority", "status")
MOBILE_DEVICE_FIELDS = (*MOBILE_DEVICE_GROUPS, "count")
MOBILE_AUTH_GROUPS = ("period", "metric", "platform", "environment", "outcome", "reason")
MOBILE_AUTH_FIELDS = (*MOBILE_AUTH_GROUPS, "count")
