"""The ``audit-trail`` report: tenant-only, CSV-only, export-only, never scheduled."""

from django.utils.translation import gettext_noop
from apps.accounts import rbac
from apps.audit.areas import READER_ACTIONS
from apps.operations.report_types import ReportDefinition
from apps.operations.report_charts_remaining import AUDIT_CHART

# Reports that read audit rows directly: each builder takes the reader as `viewer` and
# keeps only that reader's areas (#219e). `audit-top-actors` scopes by its `actor`.
# #219(e-1): area readers are admitted without VIEW_AUDIT through `alternate_actions`;
# scheduling, organization and dashboard paths still key on `required_action` alone.
AUDIT_READER_ACTIONS = READER_ACTIONS
AUDIT_VIEWER_REPORT_KEYS = frozenset({"audit-trail", "audit-activity", "audit-activity-hours"})

AUDIT_REPORT_DEFINITIONS = (
    ReportDefinition(
        "audit-trail",
        "apps.operations.reports_audit.build_audit_trail",
        ("created_at", "actor", "action", "action_label", "target_type", "target_id", "meta"),
        # The reports route already requires the `reports` module; staff_admin is core.
        required_modules=(),
        required_action=rbac.Action.VIEW_AUDIT,
        alternate_actions=AUDIT_READER_ACTIONS,
        exportable=True,
        title=gettext_noop("Audit trail"),
        chart_hint="table",
        version=1,
        chart_spec=AUDIT_CHART,
        allowed_formats=("csv",),
        # Email/chat delivery would broaden custody of accountability data.
        schedulable=False,
        # A JSON preview would be a second audit list beside /admin/audit-logs.
        previewable=False,
        # Rows must keep their tenant; no deployment-wide surface may flatten them.
        deployment_aggregate=False,
    ),
)
