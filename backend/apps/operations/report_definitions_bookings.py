"""Tenant-local resource reports retain their whole-window overlap contract."""

from .report_types import ReportDefinition

UTILIZATION_FIELDS = (
    "space_id", "space_name", "kind", "is_active", "booked", "completed", "no_show",
    "cancelled", "upcoming", "reserved_hours", "completed_hours", "window_hours",
    "reservation_utilization_percent", "no_show_rate_percent",
)
ARRIVAL_FIELDS = ("arrived_reservations", "confirmed_without_recorded_arrival")
RESOURCE_UTILIZATION_FIELDS = (*UTILIZATION_FIELDS, *ARRIVAL_FIELDS)
RESERVATION_FIELDS = (
    "booking_id", "space_id", "space_name", "name", "email", "phone",
    "starts_at", "ends_at", "status", "created_at",
)
ANSWER_FIELDS = ("booking_id", "space_id", "starts_at", "ends_at", "status", "answers")


def _definition(key, builder, fields, title, feature, **kwargs):
    return ReportDefinition(
        key, f"apps.operations.{builder}", fields, ("bookings",), title=title,
        subject_kind="bookable_space", required_feature=f"bookings.{feature}",
        schedulable=False, deployment_aggregate=False, **kwargs,
    )


BOOKING_REPORT_DEFINITIONS = (
    _definition("booking-resource-utilization", "reports_booking_resources.build_resource_utilization",
                RESOURCE_UTILIZATION_FIELDS, "Resource reservation utilization", "analytics", version=2),
    _definition("booking-resource-utilization-pdf", "reports_booking_resources.build_resource_utilization_pdf",
                RESOURCE_UTILIZATION_FIELDS, "Resource reservation utilization", "utilization_pdf", version=2,
                allowed_formats=("pdf",), pdf_renderer_path="apps.operations.reports_booking_pdf.render_pdf"),
    _definition("booking-reservations", "reports_booking_exports.build_reservations",
                RESERVATION_FIELDS, "Resource reservation export", "exports"),
    _definition("booking-answers", "reports_booking_exports.build_answers",
                ANSWER_FIELDS, "Resource reservation answers", "exports"),
)
