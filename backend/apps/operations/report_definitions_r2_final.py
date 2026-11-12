"""Release 0.12.0 reports (decision 327): device adapters, machine access grants, card studio,
event certificates, report usage and the platform profile roll-up.

All are counts only. The tenant reports are per-space and also roll up for the superadmin as
one aggregate row set per space (never merged across an organization, so they sit in the
organization exclusion list). Each reads through its module gate, needs the action named here
and is schedulable and exportable like every other registry report.
"""

from django.utils.translation import gettext_noop

from apps.accounts import rbac
from apps.operations.report_charts_remaining import table
from apps.operations.report_types import ReportDefinition

_PATH = "apps.operations."
_FIELDS = ("metric", "value")


def _counts(key, builder, modules, action, title):
    return ReportDefinition(key, f"{_PATH}{builder}", _FIELDS, modules, required_action=action, title=title,
                            chart_hint="table", chart_spec=table("metric"))


R2_FINAL_REPORT_DEFINITIONS = (
    _counts("device-adapter-activity", "reports_r2_devices.build_device_adapter_activity", ("devices",),
            rbac.Action.MANAGE_DEVICES, gettext_noop("Device adapter activity")),
    _counts("machine-access-grants", "reports_r2_devices.build_machine_access_grants", ("machines",),
            rbac.Action.MANAGE_MACHINES, gettext_noop("Machine access grants")),
    _counts("card-studio-activity", "reports_r2_cards.build_card_studio_activity", ("membership",),
            rbac.Action.MANAGE_MEMBER_CARDS, gettext_noop("Card studio activity")),
    _counts("event-certificates-issued", "reports_r2_cards.build_event_certificates_issued", ("events",),
            rbac.Action.MANAGE_EVENTS, gettext_noop("Event certificates issued")),
    _counts("report-usage", "reports_r2_usage.build_report_usage", ("reports",),
            rbac.Action.MANAGE_MAKERSPACE, gettext_noop("Report schedules and saved views")),
    ReportDefinition("platform-profile-adoption", f"{_PATH}reports_r2_profiles.build_platform_profile_adoption",
                     ("makerspace_id", "metric", "value"), required_action=rbac.Action.MANAGE_MAKERSPACE,
                     title=gettext_noop("Profile and username adoption"), platform_only=True, schedulable=False,
                     chart_hint="table", chart_spec=table("metric")),
)
R2_FINAL_REPORT_KEYS = frozenset(definition.key for definition in R2_FINAL_REPORT_DEFINITIONS)
