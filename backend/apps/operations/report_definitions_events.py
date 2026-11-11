"""Tenant-only event detail exports; the existing attendance builder owns analytics.

Keyed to MANAGE_EVENTS (not the VIEW_AUDIT default) so the built-in Event Manager runs
the exports for every event it manages; the subject check still applies per event.
"""

from django.utils.translation import gettext_noop
from apps.accounts import rbac

from .report_types import ReportDefinition
from .report_definitions_existing import EXISTING_REPORT_DEFINITIONS
from .reports_events_money import PDF_FIELDS as EVENT_PDF_FIELDS
from .reports_event_orders import ORDER_FIELDS
from .report_charts_remaining import REGISTRATIONS_CHART, FEEDBACK_CHART, ATTENDANCE_PDF_CHART

# Lane L21a appends the crew flag and the "still coming?" reply (X43).
REGISTRATION_FIELDS = ("registration_id", "name", "email", "phone", "status", "created_at", "answers",
                       "crew", "attendance_reply")
FEEDBACK_FIELDS = ("response_id", "created_at", "registration_id", "answers")
ATTENDANCE_FIELDS = next(d.fields for d in EXISTING_REPORT_DEFINITIONS if d.key == "event-attendance")

EVENT_REPORT_DEFINITIONS = (
    ReportDefinition("event-registrations", "apps.operations.reports_event_exports.build_registrations",
                     REGISTRATION_FIELDS, ("events",), required_action=rbac.Action.MANAGE_EVENTS, title=gettext_noop("Event registration export"), subject_kind="event",
                     required_feature="reports.event_exports", schedulable=False, deployment_aggregate=False,
                     chart_spec=REGISTRATIONS_CHART),
    ReportDefinition("event-feedback", "apps.operations.reports_event_exports.build_feedback",
                     FEEDBACK_FIELDS, ("events",), required_action=rbac.Action.MANAGE_EVENTS, title=gettext_noop("Event feedback export"), subject_kind="event",
                     required_feature="reports.event_exports", schedulable=False, deployment_aggregate=False,
                     chart_spec=FEEDBACK_CHART),
    # Parity C24: one row per ticket order; the staff order list's authority, plus `events.orders`.
    ReportDefinition("event-orders", "apps.operations.reports_event_orders.build_event_orders",
                     ORDER_FIELDS, ("events",), required_action=rbac.Action.MANAGE_EVENTS, title=gettext_noop("Event orders export"), subject_kind="event",
                     required_feature="reports.event_exports", allowed_formats=("csv",), schedulable=False,
                     deployment_aggregate=False),
    # Parity C19: the PDF adds Money and Spending sections when payments or charges are on and the viewer sees them.
    ReportDefinition("event-attendance-pdf", "apps.operations.reports_events_money.build_event_report_pdf",
                     EVENT_PDF_FIELDS, ("events",), required_action=rbac.Action.MANAGE_EVENTS, title=gettext_noop("Post-event analytics"), subject_kind="event",
                     required_feature="reports.event_pdf", allowed_formats=("pdf",),
                     pdf_renderer_path="apps.operations.report_pdf.render_pdf",
                     schedulable=False, deployment_aggregate=False, chart_hint="line", chart_spec=ATTENDANCE_PDF_CHART),
)
