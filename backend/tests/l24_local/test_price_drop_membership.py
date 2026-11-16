"""#163A memberships: a lowered plan price reaches paid terms that have not started yet."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.makerspaces.models import MakerspaceMembership, MembershipPlan, MembershipTerm
from apps.payments.models import Payment, Refund, RefundCase
from tests.l24_local.helpers import client, l24_space, preview
from tests.payments.refund_case_helpers import charge, member

pytestmark = pytest.mark.django_db
D = Decimal
MODULES = ("membership",)


def plan(space, amount="50.00"):
    return MembershipPlan.objects.create(makerspace=space, name="Pro", interval="monthly", amount=D(amount),
                                         currency="usd")


def term(space, user, the_plan, *, starts, days=30, **extra):
    membership = MakerspaceMembership.objects.get(makerspace=space, user=user)
    return MembershipTerm.objects.create(membership=membership, plan=the_plan, starts_at=starts,
                                         ends_at=starts + timedelta(days=days), price=the_plan.amount,
                                         currency="usd", **extra)


def plan_url(the_plan):
    return reverse("admin-membership-plan-detail", kwargs={"pk": the_plan.pk})


def test_plan_drop_reaches_a_renewal_paid_early_and_an_upcoming_term():
    space, sm = l24_space("l24-ms-drop", modules=MODULES)
    pro = plan(space)
    now = timezone.now()
    early = member("l24-ms-early", space)
    running = term(space, early, pro, starts=now - timedelta(days=10))
    renewal = charge(space, early, subject_type=Payment.SubjectType.MEMBERSHIP_TERM, subject_id=running.pk,
                     amount="50.00")
    later = member("l24-ms-later", space)
    first = term(space, later, pro, starts=now - timedelta(days=40))
    upcoming = term(space, later, pro, starts=now + timedelta(days=5), renewed_from=first, kind="renewal")
    paid_upcoming = charge(space, later, subject_type=Payment.SubjectType.MEMBERSHIP_TERM, subject_id=first.pk,
                           amount="50.00")
    started = member("l24-ms-started", space)
    old = term(space, started, pro, starts=now - timedelta(days=60))
    term(space, started, pro, starts=now - timedelta(days=30), renewed_from=old, kind="renewal")
    charge(space, started, subject_type=Payment.SubjectType.MEMBERSHIP_TERM, subject_id=old.pk, amount="50.00")
    report = preview(client(sm).patch(plan_url(pro) + "?price_drop_preview=1", {"amount": "40.00"}, format="json"))
    assert sorted((item["payment_id"], item["difference"]) for item in report["items"]) == sorted(
        [(renewal.pk, "10.00"), (paid_upcoming.pk, "10.00")])
    assert MembershipPlan.objects.get(pk=pro.pk).amount == D("50.00")
    assert client(sm).patch(plan_url(pro), {"amount": "40.00"}, format="json").status_code == 200
    opened = {case.payment_id: case for case in RefundCase.objects.all()}
    assert set(opened) == {renewal.pk, paid_upcoming.pk}
    assert all(case.reason_code == "price_drop" and case.due_amount == D("10.00") for case in opened.values())
    assert not Refund.objects.exists()


def test_plan_rise_and_switch_off_open_nothing():
    space, sm = l24_space("l24-ms-off", on=False, modules=MODULES)
    pro = plan(space)
    user = member("l24-ms-off-m", space)
    running = term(space, user, pro, starts=timezone.now() - timedelta(days=3))
    charge(space, user, subject_type=Payment.SubjectType.MEMBERSHIP_TERM, subject_id=running.pk, amount="50.00")
    assert client(sm).patch(plan_url(pro), {"amount": "30.00"}, format="json").status_code == 200
    assert not RefundCase.objects.exists()
    assert client(sm).patch(plan_url(pro) + "?price_drop_preview=1", {"amount": "20.00"},
                            format="json").status_code == 404
