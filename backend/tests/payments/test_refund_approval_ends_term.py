"""X21: approving a membership refund ends the term it paid for, unless staff keep the membership."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.makerspaces.models import MakerspaceMembership, MembershipPlan, MembershipTerm
from apps.payments.models import Payment, RefundCase
from apps.payments.services_refund_cases import request_refund
from tests.payments.refund_case_helpers import charge, member, space_with_currency
from tests.return_helpers import authenticated_client, make_member

pytestmark = pytest.mark.django_db


def _case(slug, *, upcoming=False):
    space = space_with_currency(slug)
    user = member(f"{slug}-m", space)
    membership = MakerspaceMembership.objects.get(makerspace=space, user=user)
    plan = MembershipPlan.objects.create(makerspace=space, name=slug, interval="monthly", amount=Decimal("30.00"),
                                         currency="usd")
    now = timezone.now()
    previous = MembershipTerm.objects.create(membership=membership, plan=plan, starts_at=now - timedelta(days=40),
                                             ends_at=now + timedelta(days=5) if upcoming else now - timedelta(days=10))
    start = previous.ends_at
    covered = MembershipTerm.objects.create(membership=membership, plan=plan, starts_at=start,
                                            ends_at=start + timedelta(days=30), renewed_from=previous)
    payment = charge(space, user, subject_type=Payment.SubjectType.MEMBERSHIP_TERM, subject_id=previous.pk,
                     amount="30.00")
    case = request_refund(payment, member=user, reason="Moving away")
    return space, make_member(f"{slug}-staff", space), covered, case


def _approve(space, staff, case, **extra):
    return authenticated_client(staff).post(
        reverse("refund-case-approve", args=[space.pk, case.pk]),
        {"amount": "10.00", "receipt": {"method": "cash", "reference": "R-1",
                                        "refunded_at": timezone.now().isoformat()}, **extra}, format="json")


def test_approval_ends_the_covered_term(django_capture_on_commit_callbacks):
    space, staff, covered, case = _case("rt-end")
    with django_capture_on_commit_callbacks(execute=True):
        response = _approve(space, staff, case)
    assert response.status_code == 200, response.content
    covered.refresh_from_db()
    assert covered.status == "cancelled"
    assert AuditLog.objects.filter(action="payment.refund_case_term_ended").exists()
    assert covered.status_events.last().reason == "Membership refund approved"
    # The approval decided the money: no second refund case was opened by ending the term.
    assert RefundCase.objects.filter(payment=case.payment).count() == 1


def test_keep_membership_leaves_the_term(django_capture_on_commit_callbacks):
    space, staff, covered, case = _case("rt-keep")
    with django_capture_on_commit_callbacks(execute=True):
        assert _approve(space, staff, case, keep_membership=True).status_code == 200
    covered.refresh_from_db()
    assert covered.status == "active"


def test_an_early_paid_upcoming_term_is_cancelled(django_capture_on_commit_callbacks):
    space, staff, covered, case = _case("rt-upcoming", upcoming=True)
    assert covered.starts_at > timezone.now()
    with django_capture_on_commit_callbacks(execute=True):
        _approve(space, staff, case)
    covered.refresh_from_db()
    assert covered.status == "cancelled"


def test_staff_see_the_policy_suggestion_on_the_case():
    space, staff, _covered, case = _case("rt-suggest")
    url = reverse("admin-refund-case-membership-suggestion", args=[space.pk, case.pk])
    body = authenticated_client(staff).get(url).json()
    assert "applies" in body and body["currency"] == "usd"
