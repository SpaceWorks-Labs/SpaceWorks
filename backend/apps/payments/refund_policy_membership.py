"""Membership-term bands for refund policy arithmetic (owner decision 68).

A renewal charge raised against term T pays for the NEXT term -- the one opened with
`renewed_from = T` -- so the term a membership payment covers is that successor. A paid
renewal whose successor was never opened covered nothing and is owed in full. Dues and
admission charges have no term at all and stay request-only.

Bands, measured on the covered term:
* cancelled before the term starts, or within `full_within_days` of its start -> full;
* otherwise, until the term ends -> pro rata of the unused time, or `partial_percent`,
  whichever the policy chose;
* after the term ends -> nothing.

Release 2 (L4, decisions 71/72): financial-year and fixed-end terms already END at the
financial-year end / the fixed date, so pro rata runs to that end with no special case.
A LIFETIME term has no end to pro-rate against: full within `full_within_days`, then
nothing. A paid-but-unopened next term is still owed in full (`never_started`).
"""

from decimal import Decimal

from apps.payments.models import Payment
from apps.payments.models_refund_cases import RefundPolicy

ZERO = Decimal("0.00")


def covered_term(payment):
    """The MembershipTerm a MEMBERSHIP_TERM payment paid for, or None."""
    from apps.makerspaces.models import MembershipTerm
    return (MembershipTerm.objects.select_related("plan").filter(renewed_from_id=payment.subject_id)
            .order_by("pk").first())


def term_for_payment(payment):
    """The term a membership charge bought: the renewed-into term for a renewal, the first
    term an admission opened for an admission charge; None for dues (X21)."""
    if payment.subject_type == Payment.SubjectType.MEMBERSHIP_TERM:
        return covered_term(payment)
    if payment.subject_type == Payment.SubjectType.MEMBERSHIP_TERM_START:  # #184: the term itself
        from apps.makerspaces.models import MembershipTerm
        return MembershipTerm.objects.select_related("plan").filter(pk=payment.subject_id).first()
    if payment.subject_type == Payment.SubjectType.MEMBERSHIP_REQUEST:
        from apps.makerspaces.models import MembershipTerm
        return (MembershipTerm.objects.select_related("plan").filter(admission_request_id=payment.subject_id)
                .order_by("pk").first())
    return None


def membership_policy(payment, term):
    """The plan's own rule, else the membership default for the space."""
    rows = RefundPolicy.objects.filter(makerspace_id=payment.makerspace_id, area=RefundPolicy.Area.MEMBERSHIP)
    if term is not None:
        own = rows.filter(plan_id=term.plan_id).first()
        if own is not None:
            return own
    return rows.filter(plan__isnull=True).first()


def membership_band(payment, policy, cancelled_at):
    """`(band, gross, snapshot)` for a membership term charge; None when no term applies."""
    if payment.subject_type not in (Payment.SubjectType.MEMBERSHIP_TERM, Payment.SubjectType.MEMBERSHIP_TERM_START):
        return None
    term = term_for_payment(payment)
    if term is None:
        return "never_started", payment.amount, {"term": None}
    starts, ends = term.starts_at, term.ends_at
    facts = {"term": term.pk, "plan": term.plan_id, "term_starts_at": starts.isoformat(),
             "term_ends_at": ends.isoformat(), "full_within_days": policy.full_within_days,
             "partial_mode": policy.partial_mode, "partial_percent": policy.partial_percent}
    if cancelled_at < starts or (cancelled_at - starts).total_seconds() <= policy.full_within_days * 86400:
        return "full", payment.amount, facts
    if term.is_lifetime:
        return "none", ZERO, {**facts, "lifetime": True}
    if cancelled_at >= ends:
        return "none", ZERO, facts
    if policy.partial_mode == RefundPolicy.PartialMode.PRO_RATA:
        total = Decimal(int((ends - starts).total_seconds()))
        unused = Decimal(int((ends - cancelled_at).total_seconds()))
        share = unused / total if total > 0 else Decimal(0)
        # Multiply before dividing so an exact share (20 of 30 days) yields an exact amount.
        gross = payment.amount * unused / total if total > 0 else ZERO
        return "pro_rata", gross, {**facts, "unused_share": str(share.quantize(Decimal("0.0001")))}
    return "partial", payment.amount * Decimal(policy.partial_percent) / Decimal(100), facts
