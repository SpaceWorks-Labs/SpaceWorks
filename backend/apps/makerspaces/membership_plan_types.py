"""Plan-type arithmetic: when a term ends, what it costs, and what kind of term it is.

Pure functions over a plan and dates (G16, X6, X7). `membership_plan_services.create_term`
is the one caller that writes; everything here only computes.

* rolling        -> the plan interval from the start (the shipped behaviour);
* financial_year -> the end of the space's financial year containing the start;
* fixed_end      -> local midnight after the plan's `fixed_end_date`;
* lifetime       -> `LIFETIME_ENDS_AT` (never ends, never renews).
"""
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from rest_framework.exceptions import ValidationError

from apps.makerspaces.models_membership_rules import LateRenewal, PlanType, TermKind
from apps.makerspaces.models_membership_terms import LIFETIME_ENDS_AT


def interval_end(plan, starts_at):
    if plan.interval == plan.Interval.MONTHLY:
        return starts_at + relativedelta(months=1)
    if plan.interval == plan.Interval.YEARLY:
        return starts_at + relativedelta(years=1)
    return starts_at + timedelta(days=plan.custom_days or 0)


def term_end(plan, starts_at):
    """When a term under `plan` that starts at `starts_at` (an aware datetime) ends."""
    kind = getattr(plan, "plan_type", PlanType.ROLLING) or PlanType.ROLLING
    if kind == PlanType.LIFETIME:
        return LIFETIME_ENDS_AT
    if kind == PlanType.FINANCIAL_YEAR:
        from apps.makerspaces.financial_year import fy_end_at
        return fy_end_at(plan.makerspace, starts_at)
    if kind == PlanType.FIXED_END:
        from apps.makerspaces.local_time import local_day_bounds
        return local_day_bounds(plan.makerspace, plan.fixed_end_date)[1]
    return interval_end(plan, starts_at)


def require_openable(plan, starts_at):
    """Refuse a term that would end before it starts (a fixed date already passed)."""
    if term_end(plan, starts_at) <= starts_at:
        raise ValidationError({"plan_id": "This plan's end date has already passed."})


def price_for(plan, kind):
    """The term price a plan charges for a NEW or a RENEWAL/REINSTATEMENT term."""
    return plan.amount if kind == TermKind.NEW else plan.renewal_price


def previous_term(membership, before=None):
    from apps.makerspaces.models import MembershipTerm
    rows = MembershipTerm.objects.filter(membership=membership).exclude(status=MembershipTerm.Status.CANCELLED)
    if before is not None:
        rows = rows.filter(starts_at__lt=before)
    return rows.order_by("-ends_at", "-pk").first()


def derive_kind(membership, starts_at, *, renewed_from=None):
    """NEW for a first term, RENEWAL when it follows the previous term without a gap
    (grace included), REINSTATEMENT after a gap."""
    if renewed_from is not None:
        return TermKind.RENEWAL
    before = previous_term(membership, before=starts_at + timedelta(seconds=1))
    if before is None:
        return TermKind.NEW
    grace = timedelta(days=before.plan.renewal_grace_days or 0)
    covered_until = max(before.grace_until or before.ends_at, before.ends_at + grace)
    return TermKind.RENEWAL if starts_at <= covered_until + timedelta(days=1) else TermKind.REINSTATEMENT


def late_renewal_start(plan, predecessor, now):
    """Start of a renewal opened at `now` for a predecessor that already ended.

    Backdate (default) continues from the old end; payment-day starts now. A backdated
    term that would already be over starts now instead, so a renewal never opens dead.
    """
    if now <= predecessor.ends_at:
        return predecessor.ends_at
    if plan.late_renewal == LateRenewal.PAYMENT_DAY:
        return now
    if term_end(plan, predecessor.ends_at) <= now:
        return now
    return predecessor.ends_at


def in_staff_grace(term, now):
    """Whether staff renewing `term` now is a late renewal rather than a reinstatement."""
    grace = timedelta(days=term.plan.renewal_grace_days or 0)
    return term.ends_at < now <= max(term.grace_until or term.ends_at, term.ends_at + grace)
