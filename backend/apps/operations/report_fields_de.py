"""D/E output allowlists, importable without loading separable domain models."""

UTILIZATION_FIELDS = (
    "period", "space_id", "space_name", "kind", "is_active", "booked", "completed",
    "no_show", "cancelled", "upcoming", "reserved_hours", "completed_hours", "window_hours",
    "reservation_utilization_percent", "no_show_rate_percent", "cancellation_rate_percent",
    "reservations", "terminal_reservations",
)
OCCUPANCY_FIELDS = ("period", "weekday", "hour", "occupied_hours", "window_hours", "occupancy_percent")
LEAD_FIELDS = ("period", "lead_time_bucket", "booking_count")
MEMBER_FIELDS = ("member_id", "member", "booking_count", "reserved_hours")
SIGNUP_FIELDS = ("event_id", "title", "period", "registrations", "cumulative_registrations")
FUNNEL_FIELDS = ("event_id", "title", "period", "registrations", "confirmed", "attended", "confirmation_rate_percent", "attendance_rate_percent")
CHECKIN_FIELDS = ("event_id", "title", "period", "timing_bucket", "checkin_count")
FEEDBACK_FIELDS = ("event_id", "title", "period", "question_id", "score_count", "score_total", "average_score")
REVENUE_FIELDS = (
    "event_id", "title", "period", "currency", "charge_count", "charged_amount",
    "promo_discount_amount", "collected_amount", "refunded_amount", "outstanding_amount", "net_amount",
)
