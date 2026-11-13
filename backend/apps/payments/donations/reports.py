"""Donations reports (RP-3): campaign progress and pledges, finance-only (#100).

Counts and money only. No row carries a donor's name, email, note, the 80G PAN or
address (`DonorTaxDetail`), or a pledge's/gift's link secret; those columns are never
read into a report. Amounts never mix currencies: every row has one currency. Without a
date range the campaign and pledge figures are lifetime; with one, only gifts created
(pledge periods) or received (campaign money) inside it count.
"""

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from apps.makerspaces.local_time import local_now
from apps.operations.report_types import ReportResult
from apps.payments.money import minor_unit_exponent, trim_money

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
#: Monthly-equivalent factor of one pledge period.
PER_MONTH = {"monthly": Decimal(1), "quarterly": Decimal(1) / Decimal(3), "yearly": Decimal(1) / Decimal(12)}
GENERAL = "General fund (no campaign)"

CAMPAIGN_FIELDS = ("campaign_id", "campaign", "kind", "status", "currency", "goal_amount", "raised_amount",
                   "pending_amount", "gift_count", "donor_count", "active_pledges", "pledged_per_month",
                   "percent_of_goal", "starts_at", "ends_at")
PLEDGE_FIELDS = ("campaign_id", "campaign", "currency", "pledge_state", "interval", "pledge_count",
                 "amount_per_period", "monthly_equivalent", "paid_periods", "paid_amount", "missed_periods",
                 "outstanding_amount")
PLEDGE_STATES = ("active", "missed", "paused", "cancelled")


def _spaces(makerspace_id):
    from apps.makerspaces.models import Makerspace
    from apps.operations.report_scope import scoped_ids

    return Makerspace.objects.filter(pk__in=scoped_ids(makerspace_id)).order_by("pk")


def _within(queryset, field, date_range):
    if not date_range:
        return queryset
    start, end = date_range
    if start is not None:
        queryset = queryset.filter(**{f"{field}__gte": start})
    if end is not None:
        queryset = queryset.filter(**{f"{field}__lt": end})
    return queryset


def _status(campaign, now):
    if not campaign.is_active:
        return "inactive"
    if campaign.starts_at and campaign.starts_at > now:
        return "scheduled"
    if campaign.ends_at and campaign.ends_at <= now:
        return "ended"
    return "open"


def _money(value):
    return trim_money(value or ZERO)


def _per_month(value, currency):
    """A monthly equivalent is a quotient (40 a year = 3.333...), so round it to the currency's
    own minor unit before display; stored amounts are exact and only need trimming."""
    step = Decimal(1).scaleb(-minor_unit_exponent(currency))
    return _money((value or ZERO).quantize(step, rounding=ROUND_HALF_UP))


def _campaign_rows(space, date_range):
    from apps.payments.models import Donation, DonationCampaign, DonationPledge

    now = timezone.now()
    campaigns = {row.pk: row for row in DonationCampaign.objects.filter(makerspace=space)}
    groups = defaultdict(lambda: {"raised": ZERO, "pending": ZERO, "gifts": 0, "accounts": set(), "guests": 0,
                                  "pledges": 0, "per_month": ZERO})
    for campaign in campaigns.values():
        groups[(campaign.pk, campaign.currency)]
    paid = _within(Donation.objects.filter(makerspace=space, status=Donation.Status.PAID), "paid_at", date_range)
    for campaign_id, currency, amount, donor_id in paid.values_list("campaign_id", "currency", "amount", "donor_id"):
        group = groups[(campaign_id, currency)]
        group["raised"] += amount
        group["gifts"] += 1
        if donor_id is None:
            group["guests"] += 1  # a guest gift counts as one giver; their contact is never read
        else:
            group["accounts"].add(donor_id)
    pending = _within(Donation.objects.filter(makerspace=space, status=Donation.Status.PENDING), "created_at",
                      date_range)
    for campaign_id, currency, amount in pending.values_list("campaign_id", "currency", "amount"):
        groups[(campaign_id, currency)]["pending"] += amount
    active = DonationPledge.objects.filter(makerspace=space, status=DonationPledge.Status.ACTIVE)
    for campaign_id, currency, amount, interval in active.values_list("campaign_id", "currency", "amount",
                                                                       "interval"):
        group = groups[(campaign_id, currency)]
        group["pledges"] += 1
        group["per_month"] += amount * PER_MONTH[interval]
    rows = []
    for (campaign_id, currency), group in groups.items():
        campaign = campaigns.get(campaign_id)
        goal = campaign.goal_amount if campaign and campaign.currency == currency else None
        raised = _money(group["raised"])
        rows.append({
            "campaign_id": campaign_id, "campaign": campaign.name if campaign else GENERAL,
            "kind": campaign.kind if campaign else "fund", "status": _status(campaign, now) if campaign else "open",
            "currency": currency, "goal_amount": goal, "raised_amount": raised,
            "pending_amount": _money(group["pending"]), "gift_count": group["gifts"],
            "donor_count": len(group["accounts"]) + group["guests"], "active_pledges": group["pledges"],
            "pledged_per_month": _per_month(group["per_month"], currency),
            "percent_of_goal": (raised * 100 / goal).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) if goal else None,
            "starts_at": campaign.starts_at if campaign else None, "ends_at": campaign.ends_at if campaign else None,
        })
    rows.sort(key=lambda row: (row["campaign_id"] is None, row["campaign"].lower(), row["currency"]))
    return rows


def build_campaign_progress(makerspace_id, *, limit=None, date_range=None, actor=None):
    records = []
    for space in _spaces(makerspace_id):
        records.extend(_campaign_rows(space, date_range))
    return ReportResult(CAMPAIGN_FIELDS, records if limit is None else records[:limit], {
        "definition": "Per campaign (and the general fund) and currency: money received against the goal, gifts "
                      "still waiting for payment, and the active pledges' monthly equivalent.",
        "columns": "donor_count = distinct signed-in givers plus each guest gift; percent_of_goal = "
                   "raised_amount / goal_amount x 100 (goal only in the campaign's own currency).",
        "privacy": "No donor names, contacts or tax identity are included.",
    })


def _pledge_state(pledge, missed):
    if pledge.status != "active":
        return pledge.status
    return "missed" if missed else "active"


def _pledge_rows(space, date_range):
    from apps.payments.donations.pledges import next_period
    from apps.payments.models import Donation, DonationPledge

    today = local_now(space).date()
    pledges = DonationPledge.objects.filter(makerspace=space).select_related("campaign").only(
        "pk", "status", "amount", "currency", "interval", "campaign", "campaign__name")
    gifts = defaultdict(list)
    period_gifts = _within(Donation.objects.filter(makerspace=space, pledge__isnull=False), "created_at", date_range)
    for pledge_id, status, amount, period_start in period_gifts.values_list("pledge_id", "status", "amount",
                                                                            "period_start"):
        gifts[pledge_id].append((status, amount, period_start))
    groups = defaultdict(lambda: {"count": 0, "per_period": ZERO, "per_month": ZERO, "paid": 0, "paid_amount": ZERO,
                                  "missed": 0, "outstanding": ZERO})
    names = {}
    for pledge in pledges:
        missed = paid = 0
        paid_amount = outstanding = ZERO
        for status, amount, period_start in gifts.get(pledge.pk, ()):
            if status == Donation.Status.PAID:
                paid, paid_amount = paid + 1, paid_amount + amount
                continue
            if status == Donation.Status.PENDING:
                outstanding += amount
            if period_start and next_period(period_start, pledge.interval) <= today:
                missed += 1  # the period is over and its gift was never paid
        key = (pledge.campaign_id, pledge.currency, _pledge_state(pledge, missed), pledge.interval)
        names[pledge.campaign_id] = pledge.campaign.name if pledge.campaign_id else GENERAL
        group = groups[key]
        group["count"] += 1
        group["per_period"] += pledge.amount
        group["per_month"] += pledge.amount * PER_MONTH[pledge.interval]
        group["paid"] += paid
        group["paid_amount"] += paid_amount
        group["missed"] += missed
        group["outstanding"] += outstanding
    rows = [{"campaign_id": campaign_id, "campaign": names[campaign_id], "currency": currency, "pledge_state": state,
             "interval": interval, "pledge_count": group["count"], "amount_per_period": _money(group["per_period"]),
             "monthly_equivalent": _per_month(group["per_month"], currency), "paid_periods": group["paid"],
             "paid_amount": _money(group["paid_amount"]), "missed_periods": group["missed"],
             "outstanding_amount": _money(group["outstanding"])}
            for (campaign_id, currency, state, interval), group in groups.items()]
    rows.sort(key=lambda row: (row["campaign_id"] is None, row["campaign"].lower(), row["currency"],
                               PLEDGE_STATES.index(row["pledge_state"]), row["interval"]))
    return rows


def build_pledges(makerspace_id, *, limit=None, date_range=None, actor=None):
    records = []
    for space in _spaces(makerspace_id):
        records.extend(_pledge_rows(space, date_range))
    return ReportResult(PLEDGE_FIELDS, records if limit is None else records[:limit], {
        "definition": "Recurring pledges per campaign, currency, state and interval, with the periods paid and "
                      "missed. A missed period is one that has ended while its gift is still unpaid.",
        "columns": "pledge_state: active (up to date), missed (active with a missed period), paused, cancelled. "
                   "outstanding_amount = period gifts still waiting for payment.",
        "privacy": "No donor names, contacts or tax identity are included.",
    })
