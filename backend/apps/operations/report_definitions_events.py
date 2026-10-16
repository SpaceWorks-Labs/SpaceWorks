"""Tenant-only event detail exports; the existing attendance builder owns analytics.

Keyed to MANAGE_EVENTS (not the VIEW_AUDIT default) so the built-in Event Manager runs
the exports for every event it manages; the subject check still applies per event.
"""

from apps.accounts import rbac

from .report_types import ReportDefinition
from .report_definitions_existing import EXISTING_REPORT_DEFINITIONS

REGISTRATION_FIELDS = ("registration_id", "name", "email", "phone", "status", "created_at", "answers")
FEEDBACK_FIELDS = ("response_id", "created_at", "registration_id", "answers")
ATTENDANCE_FIELDS = next(d.fields for d in EXISTING_REPORT_DEFINITIONS if d.key == "event-attendance")

EVENT_REPORT_DEFINITIONS = (
    ReportDefinition("event-registrations", "apps.operations.reports_event_exports.build_registrations",
                     REGISTRATION_FIELDS, ("events",), required_action=rbac.Action.MANAGE_EVENTS, title="Event registration export", subject_kind="event",
                     required_feature="reports.event_exports", schedulable=False, deployment_aggregate=False),
    ReportDefinition("event-feedback", "apps.operations.reports_event_exports.build_feedback",
                     FEEDBACK_FIELDS, ("events",), required_action=rbac.Action.MANAGE_EVENTS, title="Event feedback export", subject_kind="event",
                     required_feature="reports.event_exports", schedulable=False, deployment_aggregate=False),
    ReportDefinition("event-attendance-pdf", "apps.operations.reports_events.build_event_attendance",
                     ATTENDANCE_FIELDS, ("events",), required_action=rbac.Action.MANAGE_EVENTS, title="Post-event analytics", subject_kind="event",
                     required_feature="reports.event_pdf", allowed_formats=("pdf",),
                     pdf_renderer_path="apps.operations.report_pdf.render_pdf",
                     schedulable=False, deployment_aggregate=False),
)
