"""Tenant-local resource reports; legacy tenant utilisation stays unchanged.

Keyed to MANAGE_BOOKINGS so the built-in Booking Manager reaches every space's reports.
"""

from apps.accounts import rbac

from .report_definitions_existing import EXISTING_REPORT_DEFINITIONS
from .report_types import ReportDefinition

UTILIZATION_FIELDS = next(d.fields for d in EXISTING_REPORT_DEFINITIONS if d.key == "booking-utilization")
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
        subject_kind="bookable_space", required_action=rbac.Action.MANAGE_BOOKINGS,
        required_feature=f"bookings.{feature}",
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
