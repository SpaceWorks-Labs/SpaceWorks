"""Curated numeric metrics: dates, labels and IDs cannot become thresholds."""

NUMERIC_FIELDS = frozenset({
    "days_on_loan", "window_days", "utilisation_percent", "damaged_count", "lost_count",
    "issued_requests", "issued_units", "return_events", "returned_units", "return_quantity_unknown_events",
    "closures_with_loss", "lost_units", "damage_rate_percent", "loss_rate_percent", "out_of_stock",
    "below_reorder", "days_observed", "days_observed_out_of_stock", "opened_count", "resolved_count",
    "resolution_hours", "average_resolution_hours", "watch_count", "waiting_count", "rate_numerator",
    "rate_denominator", "rate_percent", "consumed_quantity", "reserved_quantity", "adjusted_quantity",
    "cost_total_minor", "cost_unknown_quantity", "remaining_quantity", "initial_quantity", "low_threshold",
    "low_count", "depleted_count", "depletion_percent", "items", "units", "estimated_total", "actual_total",
    "received_items", "inventoried_items", "order_hours", "order_samples", "receive_hours", "receive_samples",
    "average_order_hours", "average_receive_hours", "line_count", "expected_quantity", "counted_quantity",
    "variance_quantity", "products", "assets", "active_loans", "available_quantity", "asset_available",
    "asset_reserved", "asset_issued", "asset_damaged", "asset_lost", "asset_maintenance", "asset_retired",
    "count", "issued_quantity", "damaged_quantity", "missing_quantity", "lost_quantity",
    "times_lent", "total_quantity_lent", "requests", "items_borrowed", "total_quantity",
    "usage_entries", "usage_hours", "registrations", "confirmed", "pending_approval",
    "registered", "waitlisted", "rejected", "cancelled", "attended", "attendance_rate_percent",
    "booked", "completed", "no_show", "upcoming", "reserved_hours", "completed_hours",
    "log_count", "total_cost", "active_schedules", "overdue_schedules", "new_members",
    "active_members", "revoked_members", "pending_requests", "open_invites", "verified_members",
    "payment_count", "amount_total", "outstanding_amount", "refunded_amount", "collected_amount",
    "net_amount", "request_count", "quantity", "jobs", "total_rows", "error_rows", "warning_rows",
    "created_count", "attached_count", "unattached_count", "object_expired_count", "bytes",
    "delivery_count", "attempt_count", "success_rate_percent", "activity_count", "failure_count",
    "cohort_members", "eligible_members", "retained_members", "retention_percent", "churned_members",
    "reactivated_members", "recurring_members", "mrr", "arr", "arpu",
    "triggered_count", "sent_count", "failed_count", "skipped_count", "suppressed_count",
    "bounced_count", "complained_count", "invalid_count", "inbox_created_count", "inbox_read_count",
    "unread_count", "read_rate_percent",
})


def condition_metrics(definition):
    return tuple(field for field in definition.fields if field in NUMERIC_FIELDS)
