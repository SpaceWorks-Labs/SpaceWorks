"""Tenant-local resource reports; legacy tenant utilisation stays unchanged."""

from .report_definitions_existing import EXISTING_REPORT_DEFINITIONS
from .report_types import ReportDefinition

UTILIZATION_FIELDS = next(d.fields for d in EXISTING_REPORT_DEFINITIONS if d.key == "booking-utilization")
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
                UTILIZATION_FIELDS, "Resource reservation utilization", "analytics"),
    _definition("booking-resource-utilization-pdf", "reports_booking_resources.build_resource_utilization_pdf",
                UTILIZATION_FIELDS, "Resource reservation utilization", "utilization_pdf",
                allowed_formats=("pdf",), pdf_renderer_path="apps.operations.reports_booking_pdf.render_pdf"),
    _definition("booking-reservations", "reports_booking_exports.build_reservations",
                RESERVATION_FIELDS, "Resource reservation export", "exports"),
    _definition("booking-answers", "reports_booking_exports.build_answers",
                ANSWER_FIELDS, "Resource reservation answers", "exports"),
)
