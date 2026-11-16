"""#68 extension (L4): FY and fixed-end terms pro rata to their end; lifetime full-then-none; X20."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.makerspaces.models import MakerspaceMembership, MembershipPlan, MembershipTerm
from apps.makerspaces.models_membership_terms import LIFETIME_ENDS_AT
from apps.payments.models import Payment, RefundPolicy
from apps.payments.refund_policy import assess
from tests.payments.refund_case_helpers import charge, member, space_with_currency
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def _paid_term(slug, *, plan_type="rolling", starts_days_ago=10, ends_in_days=20, lifetime=False):
    space = space_with_currency(slug)
    user = member(f"{slug}-m", space)
    membership = MakerspaceMembership.objects.get(makerspace=space, user=user)
    now = timezone.now()
    fixed = (now + timedelta(days=ends_in_days)).date() if plan_type == "fixed_end" else None
    plan = MembershipPlan.objects.create(makerspace=space, name=slug, interval="yearly", amount=Decimal("30.00"),
                                         currency="usd", plan_type=plan_type, fixed_end_date=fixed)
    previous = MembershipTerm.objects.create(membership=membership, plan=plan, starts_at=now - timedelta(days=400),
                                             ends_at=now - timedelta(days=starts_days_ago))
    start = now - timedelta(days=starts_days_ago)
    covered = MembershipTerm.objects.create(
        membership=membership, plan=plan, starts_at=start, renewed_from=previous, plan_type=plan_type,
        ends_at=LIFETIME_ENDS_AT if lifetime else now + timedelta(days=ends_in_days))
    payment = charge(space, user, subject_type=Payment.SubjectType.MEMBERSHIP_TERM, subject_id=previous.pk,
                     amount="30.00")
    RefundPolicy.objects.create(makerspace=space, area="membership", full_within_days=3, partial_mode="pro_rata",
                                partial_percent=0, cancellation_fee=Decimal("0.00"))
    return space, user, covered, payment, now


def test_fy_term_is_pro_rata_to_its_financial_year_end():
    _space, _user, _covered, payment, now = _paid_term("rf-fy", plan_type="financial_year")
    due, snapshot = assess(payment, reason_code="membership_cancelled", cancelled_at=now)
    assert snapshot["band"] == "pro_rata" and due == Decimal("20.00")


def test_fixed_end_term_is_pro_rata_too():
    _space, _user, _covered, payment, now = _paid_term("rf-fixed", plan_type="fixed_end")
    assert assess(payment, reason_code="membership_cancelled", cancelled_at=now)[1]["band"] == "pro_rata"


def test_lifetime_is_full_inside_the_window_then_nothing():
    _space, _user, covered, payment, now = _paid_term("rf-life", plan_type="lifetime", starts_days_ago=1, lifetime=True)
    assert assess(payment, reason_code="membership_cancelled", cancelled_at=now)[0] == Decimal("30.00")
    later = covered.starts_at + timedelta(days=30)
    due, snapshot = assess(payment, reason_code="membership_cancelled", cancelled_at=later)
    assert due == Decimal("0.00") and snapshot["band"] == "none" and snapshot["lifetime"] is True


def test_member_sees_the_suggested_amount_before_asking():
    space, user, _covered, payment, _now = _paid_term("rf-suggest")
    url = reverse("member-refund-suggestion", args=[space.pk, payment.pk])
    body = authenticated_client(user).get(url).json()
    # Pro rata of the unused time, measured at the request instant: just under 20.00.
    assert body["applies"] is True and Decimal("19.90") <= Decimal(body["suggested_amount"]) <= Decimal("20.00")
    from tests.payments.refund_case_helpers import membership_charge
    other = membership_charge(space, user)  # dues have no term: the policy suggests nothing
    assert authenticated_client(user).get(reverse("member-refund-suggestion", args=[space.pk, other.pk])).json()["applies"] is False
