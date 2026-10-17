"""Output schemas stay importable even when a source app is tombstoned."""

PRESENCE_FIELDS = ("period", "visits", "unique_visitors", "declared_presence_seconds", "average_declared_presence_seconds")
AUDIT_FIELDS = ("period", "action", "count")
HOUR_FIELDS = ("weekday", "hour", "count", "declared_presence_seconds")
PERSON_FIELDS = ("person_id", "count", "declared_presence_seconds")
DEVICE_FIELDS = (
    "period", "device_id", "online_seconds", "offline_seconds", "unknown_seconds", "uptime_percent",
    "offline_incidents", "commands", "commands_acknowledged", "commands_failed", "command_success_percent",
    "label_prints", "labels_printed", "label_failures",
)
DEVICE_SUM_FIELDS = ("online_seconds", "offline_seconds", "unknown_seconds", "offline_incidents", "commands",
                     "commands_acknowledged", "commands_failed", "label_prints", "labels_printed", "label_failures")
HEALTH_FIELDS = ("module_key", "enabled", "runtime_available", "coverage_kind", "activity_count", "failure_count",
                 "last_activity_at", "rollup_watermark", "rollup_state", "period", "delivery_kind", "delivery_count", "success_count", "success_rate_percent")
ORGANIZATION_FIELDS = ("period", "organization_id", "invitations", "redeemed", "revoked", "expired", "open_invitations",
                       "memberships", "active_memberships", "suspended_memberships", "redemption_percent")
ORGANIZATION_COUNTS = ORGANIZATION_FIELDS[2:-1]
SERVICES_FIELDS = ("makerspace_id", "period", "day", "service", "provider_source", "status", "bucket", "count", "currency", "amount")
USAGE_FIELDS = ("makerspace_id", "period", "metric", "entity_kind", "entity_id", "unit", "currency", "value")
