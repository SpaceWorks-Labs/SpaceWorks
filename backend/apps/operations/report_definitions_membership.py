from django.utils.translation import gettext_lazy
from apps.accounts import rbac
from apps.operations.report_types import ReportDefinition
from apps.operations.reports_retention import FIELDS as RETENTION_FIELDS
from apps.operations.reports_membership_revenue import FIELDS as REVENUE_FIELDS
from apps.operations.reports_membership_growth import FIELDS as GROWTH_FIELDS
from apps.operations.report_charts_fg import GROWTH_CHART, RETENTION_CHART, MEMBERSHIP_REVENUE_CHART
from apps.operations.org_report_aggregate import register_combine
from apps.operations.org_report_fg import combine_growth, combine_retention, combine_membership_revenue

MEMBERSHIP_REPORT_DEFINITIONS = (
    ReportDefinition("membership-growth", "apps.operations.reports_membership_growth.build_membership_growth",
                     GROWTH_FIELDS, ("membership",), title=gettext_lazy("Membership growth"), chart_hint="line",
                     grains=("day", "week", "month"), chart_spec=GROWTH_CHART),
    ReportDefinition("member-retention", "apps.operations.reports_retention.build_member_retention",
                     RETENTION_FIELDS, ("membership",), title=gettext_lazy("Member retention and cohorts"),
                     version=2, chart_hint="heatmap", chart_spec=RETENTION_CHART),
    ReportDefinition("membership-revenue", "apps.operations.reports_membership_revenue.build_membership_revenue",
                     REVENUE_FIELDS, ("membership",), required_action=rbac.Action.VIEW_FINANCE,
                     title=gettext_lazy("Membership MRR / ARR per plan"), grains=("month", "week", "day"), version=2,
                     chart_hint="line", chart_spec=MEMBERSHIP_REVENUE_CHART),
)

from apps.operations.report_definitions_membership_l4 import L4_MEMBERSHIP_REPORT_DEFINITIONS  # noqa: E402
MEMBERSHIP_REPORT_DEFINITIONS += L4_MEMBERSHIP_REPORT_DEFINITIONS
from apps.operations.report_definitions_cards import CARD_REPORT_DEFINITIONS  # noqa: E402
MEMBERSHIP_REPORT_DEFINITIONS += CARD_REPORT_DEFINITIONS

register_combine("membership-growth", combine_growth)
register_combine("member-retention", combine_retention)
register_combine("membership-revenue", combine_membership_revenue)
