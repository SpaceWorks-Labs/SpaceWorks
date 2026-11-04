"""RP-3 donations reports: campaign progress, pledges and sponsor perks (release 2, after L18).

Finance-only like every L18 staff surface: `view_finance` (the Space Manager and finance
staff, #100). Each report sits behind its own L18 switch, runs per space only, and never
carries a donor's name or contact, the 80G PAN or address, a link secret or a sponsor's
private contact. The donations money itself is the ledger area `finance-donations`.
"""

from apps.accounts import rbac
from apps.operations.report_charts_remaining import table
from apps.operations.report_types import ReportDefinition
from apps.operations.reports_de_common import chart
from apps.payments.donations.reports import CAMPAIGN_FIELDS, PLEDGE_FIELDS
from apps.payments.donations.reports_sponsors import PERK_FIELDS

_DONATIONS = "apps.payments.donations."

CAMPAIGN_CHART = chart("campaign", (("raised_amount", "currency_major"), ("goal_amount", "currency_major"),
                                    ("pending_amount", "currency_major")), currency=True, top=10)
PLEDGE_CHART = chart("campaign", (("pledge_count", "pledges"), ("missed_periods", "periods")),
                     series=("pledge_state",), tenant=False, top=10)
PERK_CHART = table("perk_id")


def _donations(key, builder, fields, title, feature, chart_spec, chart_hint):
    return ReportDefinition(key, _DONATIONS + builder, fields, required_action=rbac.Action.VIEW_FINANCE,
                            title=title, deployment_aggregate=False, required_feature=feature,
                            chart_hint=chart_hint, chart_spec=chart_spec)


DONATION_REPORT_DEFINITIONS = (
    _donations("donations-campaign-progress", "reports.build_campaign_progress", CAMPAIGN_FIELDS,
               "Donation campaigns against their goals", "finance.donations", CAMPAIGN_CHART, "grouped_bar"),
    _donations("donations-pledges", "reports.build_pledges", PLEDGE_FIELDS,
               "Recurring pledges: active, missed, paused and cancelled", "finance.recurring_donations",
               PLEDGE_CHART, "stacked_bar"),
    _donations("donations-sponsor-perks", "reports_sponsors.build_sponsor_perks", PERK_FIELDS,
               "Sponsor perks due and fulfilled", "finance.sponsors", PERK_CHART, "table"),
)
DONATION_REPORT_KEYS = frozenset(definition.key for definition in DONATION_REPORT_DEFINITIONS)
