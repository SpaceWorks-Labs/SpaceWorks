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
                     GROWTH_FIELDS, ("membership",), title="Membership growth", chart_hint="line",
                     grains=("day", "week", "month"), chart_spec=GROWTH_CHART),
    ReportDefinition("member-retention", "apps.operations.reports_retention.build_member_retention",
                     RETENTION_FIELDS, ("membership",), title="Member retention and cohorts",
                     version=2, chart_hint="heatmap", chart_spec=RETENTION_CHART),
    ReportDefinition("membership-revenue", "apps.operations.reports_membership_revenue.build_membership_revenue",
                     REVENUE_FIELDS, ("membership",), required_action=rbac.Action.VIEW_FINANCE,
                     title="Membership MRR / ARR per plan", grains=("month", "week", "day"), version=2,
                     chart_hint="line", chart_spec=MEMBERSHIP_REVENUE_CHART),
)

register_combine("membership-growth", combine_growth)
register_combine("member-retention", combine_retention)
register_combine("membership-revenue", combine_membership_revenue)
