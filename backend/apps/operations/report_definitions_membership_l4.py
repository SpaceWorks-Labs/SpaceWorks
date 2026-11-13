"""Release-2 L4 membership report definitions (G19, X14, X33, X34).

All tenant-local (`deployment_aggregate=False`) and excluded from organisation totals.
Each sits behind its capability through `required_feature`; the two person lists are
identity-bearing (unschedulable; a superadmin needs an open PII window) and the counts
are `manage_members` reports -- membership money is visible to membership managers (#100).
"""
from apps.accounts import rbac
from apps.operations.report_charts_fg import chart
from apps.operations.report_charts_remaining import table
from apps.operations.report_types import ReportDefinition
from apps.operations.reports_membership_l4_lists import (
    BREAKDOWN_FIELDS, EXPIRY_FIELDS, FUNNEL_FIELDS, REGISTER_FIELDS, WINBACK_FIELDS,
)
from apps.operations.reports_membership_l4_terms import BRIDGE_FIELDS, RENEWAL_FIELDS
from apps.operations.reports_membership_summary import FIELDS as SUMMARY_FIELDS

_LISTS = "apps.operations.reports_membership_l4_lists."
_TERMS = "apps.operations.reports_membership_l4_terms."
_INSIGHTS = "membership.insights"


def _tenant_local(spec):
    """These reports never aggregate across spaces, so they declare no tenant partition."""
    return {**spec, "partition": None}


def _insight(key, builder, fields, title, *, feature=_INSIGHTS, grains=(), identity=False, spec=None, hint="table"):
    return ReportDefinition(
        key, builder, fields, ("membership",), required_action=rbac.Action.MANAGE_MEMBERS, title=title,
        grains=grains, required_feature=feature, deployment_aggregate=False, identity_bearing=identity,
        schedulable=not identity, chart_hint=hint, chart_spec=_tenant_local(spec) if spec else table(fields[0]),
    )


RENEWAL_CHART = chart("period", [("due", "memberships"), ("renewed", "memberships")], time=True,
                      series=("currency",), alt="{period}: {renewed} of {due} terms renewed.")
BRIDGE_CHART = chart("period", [(field, "memberships") for field in ("joined", "came_back", "lapsed", "revoked", "end")],
                     time=True, alt="{period}: {end} members in good standing at the end.")
FUNNEL_CHART = chart("period", [(field, "memberships") for field in ("submitted", "approved", "rejected")],
                     time=True, alt="{period}: {submitted} join requests, {approved} approved.")
EXPIRY_CHART = chart("week_start", [("terms_ending", "memberships")], time=True, series=("currency",),
                     alt="Week of {week_start}: {terms_ending} terms ending.")


L4_MEMBERSHIP_REPORT_DEFINITIONS = (
    _insight("membership-renewals", _TERMS + "build_membership_renewals", RENEWAL_FIELDS,
             "Renewals, first-year renewals and collection", grains=("month", "week"), spec=RENEWAL_CHART, hint="bar"),
    _insight("membership-bridge", _TERMS + "build_membership_bridge", BRIDGE_FIELDS,
             "Membership bridge", grains=("month", "week"), spec=BRIDGE_CHART, hint="bar"),
    _insight("membership-breakdown", _LISTS + "build_membership_breakdown", BREAKDOWN_FIELDS,
             "Member breakdowns"),
    _insight("membership-expiry-calendar", _LISTS + "build_membership_expiry_calendar", EXPIRY_FIELDS,
             "Expiry calendar (13 weeks)", spec=EXPIRY_CHART, hint="bar"),
    _insight("membership-applications-funnel", _LISTS + "build_membership_applications_funnel", FUNNEL_FIELDS,
             "Applications funnel", grains=("month", "week"), spec=FUNNEL_CHART, hint="bar"),
    _insight("membership-win-back", _LISTS + "build_membership_win_back", WINBACK_FIELDS,
             "Win-back list", identity=True),
    _insight("member-register", _LISTS + "build_member_register", REGISTER_FIELDS,
             "Member register", feature="membership.register_tools", identity=True),
    _insight("membership-monthly-summary", "apps.operations.reports_membership_summary.build_membership_monthly_summary",
             SUMMARY_FIELDS, "Monthly membership summary", feature="membership.monthly_summary"),
)
L4_MEMBERSHIP_REPORT_KEYS = frozenset(definition.key for definition in L4_MEMBERSHIP_REPORT_DEFINITIONS)
