"""Release 0.12.0 "Web and app use" reports: channel split of sessions and calls, counts only.

``platform-channel-usage`` is the superadmin roll-up (every servable space, plus the deployment's
unattributed rows); ``channel-usage`` is the per-space variant for a Space Manager holding
``view_analytics`` there. Neither combines across an organization: session-days and local
calendars are tenant-local.
"""

from django.utils.translation import gettext_noop

from apps.accounts import rbac
from apps.operations.report_fields_channels import CHANNEL_USAGE_FIELDS
from apps.operations.report_types import ReportDefinition
from apps.operations.reports_j_common import chart

_PATH = "apps.operations.reports_channel_usage."
_SPEC = chart("period", (("value", "count"),), series=("measure", "channel", "area"), partition=None, top=10)
_GRAINS = ("day", "week", "month")

CHANNEL_REPORT_DEFINITIONS = (
    ReportDefinition(
        "channel-usage", f"{_PATH}build_channel_usage", CHANNEL_USAGE_FIELDS, ("reports",),
        required_action=rbac.Action.VIEW_ANALYTICS, title=gettext_noop("Web and app use"),
        grains=_GRAINS, chart_hint="stacked_bar", chart_spec=_SPEC, version=1),
    ReportDefinition(
        "platform-channel-usage", f"{_PATH}build_platform_channel_usage", ("makerspace_id", *CHANNEL_USAGE_FIELDS),
        required_action=rbac.Action.MANAGE_MAKERSPACE, title=gettext_noop("Web and app use"),
        platform_only=True, schedulable=False, grains=_GRAINS, chart_hint="stacked_bar", chart_spec=_SPEC, version=1),
)
CHANNEL_REPORT_KEYS = frozenset(d.key for d in CHANNEL_REPORT_DEFINITIONS)
