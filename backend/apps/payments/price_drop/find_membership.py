"""Paid membership fees for terms not yet started that would cost less now (#163A).

Two kinds of paid-but-unused term, both on the plan whose price was saved:

* an UPCOMING term (starts later) paid by its admission charge or by the renewal charge
  of the term before it -- its frozen `price` against the plan's price for that kind of
  term today;
* a RENEWAL already paid while the current term still runs, whose next term has not
  been opened yet -- the renewal amount charged against the plan's renewal price today.

The item is the charge (one charge buys one term), so a renewal paid early keeps its
history when its term opens. Only the dues are re-priced: a joining fee is not a plan
price. Approving one of these cases never ends the term (`approval.is_difference_case`).
"""

from decimal import Decimal

from django.utils import timezone

from apps.payments.models import Payment
from apps.payments.price_drop.shares import SETTLED, Affected, by_total

MT = Payment.SubjectType.MEMBERSHIP_TERM
MR = Payment.SubjectType.MEMBERSHIP_REQUEST


def _charge_for(term):
    if term.renewed_from_id:
        return MT, term.renewed_from_id
    if term.admission_request_id:
        return MR, term.admission_request_id
    return None, None


def _paid(makerspace, subject_type, subject_id):
    return (Payment.objects.filter(makerspace=makerspace, subject_type=subject_type, subject_id=subject_id,
                                   status__in=SETTLED).prefetch_related("refund_cases").first())


def _affected(plan, payment, before, after, starts_at, term_id):
    result = by_total(payment, f"membership_charge:{payment.pk}", before=before, after=after, ratio=Decimal(1))
    if result is None:
        return None
    baseline, owed = result
    return Affected(area="membership", item_type="membership_charge", item_id=payment.pk, label=plan.name,
                    payment=payment, before=baseline, after=Decimal(after), difference=owed, starts_at=starts_at,
                    facts={"plan_id": plan.pk, "term_id": term_id})


def find_membership(plan):
    from apps.makerspaces.membership_plan_types import price_for
    from apps.makerspaces.models import MembershipTerm

    makerspace, now, found = plan.makerspace, timezone.now(), []
    upcoming = MembershipTerm.objects.filter(plan=plan, status=MembershipTerm.Status.ACTIVE, starts_at__gt=now,
                                             price__isnull=False).order_by("starts_at", "pk")
    for term in upcoming:
        subject_type, subject_id = _charge_for(term)
        payment = _paid(makerspace, subject_type, subject_id) if subject_type else None
        if payment is None or payment.currency != (term.currency or payment.currency):
            continue
        row = _affected(plan, payment, term.price, price_for(plan, term.kind), term.starts_at, term.pk)
        if row is not None:
            found.append(row)
    running = MembershipTerm.objects.filter(plan=plan, status=MembershipTerm.Status.ACTIVE, starts_at__lte=now,
                                            ends_at__gt=now, next_term__isnull=True)
    for term in running.order_by("ends_at", "pk"):
        payment = _paid(makerspace, MT, term.pk)
        if payment is None:
            continue
        row = _affected(plan, payment, payment.amount, plan.renewal_price, term.ends_at, None)
        if row is not None:
            found.append(row)
    return found
