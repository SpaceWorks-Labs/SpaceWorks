"""Owner decision 68: membership terms get a refund policy, per plan, with pro rata."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.makerspaces.models import MakerspaceMembership, MembershipPlan, MembershipTerm
from apps.payments.models import Payment, RefundCase, RefundPolicy
from apps.payments.refund_policy import assess
from tests.payments.refund_case_helpers import charge, member, space_with_currency
from tests.return_helpers import authenticated_client, make_member

pytestmark = pytest.mark.django_db


def setup(slug, *, currency="usd", amount="30.00", started_days_ago=10, length_days=30, successor=True):
    space = space_with_currency(slug, currency)
    user = member(f"{slug}-m", space)
    membership = MakerspaceMembership.objects.get(makerspace=space, user=user)
    plan = MembershipPlan.objects.create(makerspace=space, name=f"{slug} plan", interval="monthly",
                                         amount=Decimal(amount), currency=currency)
    now = timezone.now()
    first = MembershipTerm.objects.create(membership=membership, plan=plan, starts_at=now - timedelta(days=60),
                                          ends_at=now - timedelta(days=started_days_ago))
    covered = None
    if successor:
        start = now - timedelta(days=started_days_ago)
        covered = MembershipTerm.objects.create(membership=membership, plan=plan, starts_at=start,
                                                ends_at=start + timedelta(days=length_days), renewed_from=first)
    # The renewal raised against `first` paid for `covered`.
    payment = charge(space, user, subject_type=Payment.SubjectType.MEMBERSHIP_TERM, subject_id=first.pk,
                     amount=amount, currency=currency)
    return space, plan, covered, payment, now


def policy(space, plan=None, *, days=3, mode="pro_rata", percent=0, fee="0.00"):
    return RefundPolicy.objects.create(makerspace=space, area="membership", plan=plan, full_within_days=days,
                                       partial_mode=mode, partial_percent=percent, cancellation_fee=Decimal(fee))


@pytest.mark.parametrize("currency,amount,expected", [
    ("usd", "30.00", Decimal("20.00")),
    ("jpy", "1000.00", Decimal("666")),     # zero-decimal: 666.67 rounds DOWN to whole yen
    ("bhd", "10.00", Decimal("6.66")),      # three-decimal, stored at two: 6.666 -> 6.66
])
def test_pro_rata_refunds_the_unused_share_rounded_down(currency, amount, expected):
    space, _, _, payment, now = setup(f"mem-pr-{currency}", currency=currency, amount=amount)
    policy(space)
    due, snapshot = assess(payment, reason_code="membership_cancelled", cancelled_at=now)
    assert due == expected and snapshot["band"] == "pro_rata" and snapshot["unused_share"] == "0.6667"


def test_full_window_percent_mode_fee_and_after_the_term():
    space, plan, covered, payment, now = setup("mem-bands")
    policy(space, days=14, mode="percent", percent=50)
    assert assess(payment, reason_code="membership_cancelled", cancelled_at=now)[0] == Decimal("30.00")
    RefundPolicy.objects.filter(makerspace=space).update(full_within_days=3, cancellation_fee=Decimal("5.00"))
    due, snapshot = assess(payment, reason_code="membership_cancelled", cancelled_at=now)
    assert due == Decimal("10.00") and snapshot["band"] == "partial" and snapshot["fee_applied"] == "5.00"
    after = covered.ends_at + timedelta(hours=1)
    assert assess(payment, reason_code="membership_cancelled", cancelled_at=after)[1]["band"] == "none"
    before = covered.starts_at - timedelta(hours=1)
    assert assess(payment, reason_code="membership_cancelled", cancelled_at=before)[0] == Decimal("25.00")  # full, minus the fee


def test_a_plan_rule_overrides_the_membership_default():
    space, plan, _, payment, now = setup("mem-plan-rule")
    policy(space, days=0, mode="percent", percent=10)
    policy(space, plan, days=0, mode="percent", percent=80)
    assert assess(payment, reason_code="membership_cancelled", cancelled_at=now)[0] == Decimal("24.00")


def test_a_renewal_whose_term_never_opened_is_owed_in_full_and_dues_stay_request_only():
    space, _, _, payment, now = setup("mem-never", successor=False)
    policy(space)
    due, snapshot = assess(payment, reason_code="membership_cancelled", cancelled_at=now)
    assert due == Decimal("30.00") and snapshot["band"] == "never_started"
    user = payment.member
    dues = charge(space, user, subject_type=Payment.SubjectType.MAKERSPACE_MEMBERSHIP,
                  subject_id=MakerspaceMembership.objects.get(makerspace=space, user=user).pk)
    assert assess(dues, reason_code="membership_cancelled")[1]["rule"] == "no_reference_time"


def test_cancelling_a_paid_term_opens_a_due_but_do_not_renew_does_not(django_capture_on_commit_callbacks):
    from apps.makerspaces.membership_plan_services import cancel_term
    from apps.makerspaces.membership_self_service import cancel_renewal
    space, _, covered, payment, _ = setup("mem-hook")
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"membership"})
    space.enabled_features = sorted(set(space.enabled_features or []) | {"membership.self_service"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    policy(space)
    staff = make_member("mem-hook-staff", space)
    own_renewal = charge(space, payment.member, subject_type=Payment.SubjectType.MEMBERSHIP_TERM,
                         subject_id=covered.pk, status="pending")
    MembershipTerm.objects.filter(pk=covered.pk).update(renewal_payment=own_renewal)
    MembershipTerm.objects.filter(pk=covered.renewed_from_id).update(renewal_payment=payment)
    covered.refresh_from_db()
    cancel_renewal(payment.member, space.pk, "moving")
    assert not RefundCase.objects.exists()
    assert Payment.objects.get(pk=own_renewal.pk).status == "canceled"
    cancel_term(staff, covered)
    case = RefundCase.objects.get(payment=payment)
    assert (case.kind, case.area, case.reason_code) == ("due", "membership", "membership_cancelled")
    assert Decimal("19.98") <= case.due_amount <= Decimal("20.00")


def test_plan_policy_api_and_membership_only_fields():
    space, plan, _, _, _ = setup("mem-api")
    manager = make_member("mem-api-manager", space)
    client = authenticated_client(manager)
    url = reverse("refund-policy-plan", args=[space.pk, plan.pk])
    body = {"full_within_days": 7, "partial_mode": "pro_rata", "partial_percent": 0, "cancellation_fee": "1.00"}
    saved = client.put(url, body, format="json")
    assert saved.status_code == 200 and saved.data["plan"] == plan.pk and saved.data["plan_name"] == plan.name
    listed = client.get(reverse("refund-policy-list", args=[space.pk])).data
    assert [row["area"] for row in listed] == ["events", "bookings", "membership", "membership"]
    events = reverse("refund-policy-detail", args=[space.pk, "events"])
    assert client.put(events, {**body, "full_within_days": 0}, format="json").status_code == 400
    other = MembershipPlan.objects.create(makerspace=space_with_currency("mem-api-other"), name="x", interval="monthly")
    assert client.put(reverse("refund-policy-plan", args=[space.pk, other.pk]), body, format="json").status_code == 404
    assert client.delete(url).status_code == 204 and not RefundPolicy.objects.filter(plan=plan).exists()
