"""Parity O-B3 report definitions: cash in hand per collector, collected revenue by plan, the 30/60/90-day
renewal forecast, application approval times and (wave 3, after member units) the unit and level leagues.

All tenant-local (`deployment_aggregate=False`) and excluded from organisation totals: money is per space, a
median cannot be averaged, and a collector's balance belongs to one space's cash drawer. Money reports need
`view_finance`; the two membership insights need `manage_members` and the existing `membership.insights`
switch, exactly like the other L4 insights. None names a member, so none is identity-bearing. The two leagues need `manage_members` and `membership.units`; a
unit-scoped actor reads their own subtree only (`member_unit_scope`).
"""
from django.utils.translation import gettext_noop

from apps.accounts import rbac
from apps.operations.report_charts_fg import chart
from apps.operations.report_types import ReportDefinition
from apps.operations.reports_approval_times import FIELDS as APPROVAL_FIELDS
from apps.operations.reports_cash_in_hand import FIELDS as CASH_FIELDS
from apps.operations.reports_renewal_forecast import FIELDS as FORECAST_FIELDS
from apps.operations.reports_revenue_by_plan import FIELDS as REVENUE_FIELDS
from apps.operations.reports_unit_league import LEVEL_FIELDS, UNIT_FIELDS

_OPS = "apps.operations."
CASH_CHART = chart("collector", [("cash_in_hand", "currency_major")], money=True, negatives="allow",
                   alt="{collector}: {cash_in_hand} {currency} in hand.")
REVENUE_CHART = chart("period", [("collected", "currency_major"), ("refunded", "currency_major"),
                                 ("net", "currency_major")], time=True, money=True, series=("plan_name",),
                      negatives="allow", alt="{period}: {net} {currency} net from {plan_name}.")
FORECAST_CHART = chart("horizon_days", [("expected_amount", "currency_major")], money=True,
                       alt="Next {horizon_days} days: {expected_amount} {currency} due on {terms_ending} terms.")
# Not money and not per-tenant: the partition is declared None, as the other tenant-local insights do.
APPROVAL_CHART = {**chart("period", [("median_hours", "hours"), ("p90_hours", "hours")], time=True,
                          alt="{period}: median {median_hours} hours, 90th percentile {p90_hours} hours."),
                  "partition": None}

# Tenant-local like the approval times: no makerspace_id column, so no tenant partition.
UNIT_LEAGUE_CHART = {**chart("unit_name", [("members", "memberships"), ("joined", "memberships")],
                             alt="{unit_name}: {members} active members, {joined} joined in the period."),
                     "partition": None}
LEVEL_LEAGUE_CHART = {**chart("level_name", [("units", "units"), ("members", "memberships")],
                              alt="{level_name}: {units} units with {members} members."),
                      "partition": None}


def _definition(key, builder, fields, title, spec, modules=(), **extra):
    return ReportDefinition(key, _OPS + builder, fields, modules, deployment_aggregate=False, title=title, chart_spec=spec,
                            **extra)


ORG_PARITY_REPORT_DEFINITIONS = (
    _definition("cash-in-hand", "reports_cash_in_hand.build_cash_in_hand", CASH_FIELDS,
                gettext_noop("Cash in hand per collector"), CASH_CHART, required_action=rbac.Action.VIEW_FINANCE,
                chart_hint="bar"),
    _definition("membership-revenue-by-plan", "reports_revenue_by_plan.build_revenue_by_plan", REVENUE_FIELDS,
                gettext_noop("Collected membership revenue by plan"), REVENUE_CHART, ("membership",),
                required_action=rbac.Action.VIEW_FINANCE, required_feature="membership.insights",
                chart_hint="grouped_bar"),
    _definition("membership-renewal-forecast", "reports_renewal_forecast.build_renewal_forecast", FORECAST_FIELDS,
                gettext_noop("Renewal forecast (30, 60 and 90 days)"), FORECAST_CHART, ("membership",),
                required_action=rbac.Action.MANAGE_MEMBERS, required_feature="membership.insights",
                chart_hint="bar"),
    _definition("membership-approval-times", "reports_approval_times.build_membership_approval_times",
                APPROVAL_FIELDS, gettext_noop("Time to approve a membership application"), APPROVAL_CHART,
                ("membership",), required_action=rbac.Action.MANAGE_MEMBERS, required_feature="membership.insights",
                grains=("month", "week"), chart_hint="bar"),
    _definition("membership-unit-league", "reports_unit_league.build_unit_league", UNIT_FIELDS,
                gettext_noop("Unit league"), UNIT_LEAGUE_CHART, ("membership",),
                required_action=rbac.Action.MANAGE_MEMBERS, required_feature="membership.units", chart_hint="bar"),
    _definition("membership-level-league", "reports_unit_league.build_level_league", LEVEL_FIELDS,
                gettext_noop("Level league"), LEVEL_LEAGUE_CHART, ("membership",),
                required_action=rbac.Action.MANAGE_MEMBERS, required_feature="membership.units", chart_hint="bar"),
)
ORG_PARITY_REPORT_KEYS = frozenset(definition.key for definition in ORG_PARITY_REPORT_DEFINITIONS)
