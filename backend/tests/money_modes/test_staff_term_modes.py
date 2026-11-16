"""#184: a membership term staff open from the console follows the membership money mode."""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.makerspaces.membership_plan_services import cancel_term, create_term
from apps.makerspaces.membership_term_charges import raise_term_start
from apps.makerspaces.models import MakerspaceMembership, MembershipPlan
from tests.makerspaces.test_membership_admission_matrix import _setup
from tests.makerspaces.test_membership_j1 import member_role
from tests.money_modes.helpers import MODES, OFFLINE, assert_mode_outcome, charges, fake_provider, set_mode

pytestmark = pytest.mark.django_db(transaction=True)
SUBJECT = "membership_term_start"


def _member(makerspace, applicant):
    return MakerspaceMembership.objects.create(makerspace=makerspace, user=applicant, assigned_role=member_role(makerspace),
                                               role="custom", status="active", activated_at=timezone.now())


@pytest.mark.parametrize("mode", MODES)
def test_a_staff_opened_paid_term_charges_in_its_mode(mode, monkeypatch, django_capture_on_commit_callbacks):
    makerspace, actor, applicant, plan, _ = _setup(paid=True)
    set_mode(makerspace, "membership", mode)
    checkout = fake_provider(monkeypatch) if mode == "online" else None
    membership = _member(makerspace, applicant)
    with django_capture_on_commit_callbacks(execute=True):
        term = create_term(actor, membership, plan)
        raise_term_start(actor, term)
    payment = assert_mode_outcome(mode, charges(makerspace, SUBJECT), checkout)
    if payment is not None:
        assert payment.amount == Decimal("20.00") and payment.member_id == applicant.pk


def test_a_free_plan_term_raises_nothing():
    makerspace, actor, applicant, _, _ = _setup(paid=False)
    set_mode(makerspace, "membership", OFFLINE)
    plan = MembershipPlan.objects.create(makerspace=makerspace, name="Free", interval="monthly", amount=Decimal("0"), currency="usd")
    raise_term_start(actor, create_term(actor, _member(makerspace, applicant), plan))
    assert charges(makerspace, SUBJECT) == []


def test_the_console_route_raises_it_and_cancelling_the_term_voids_the_pending_charge():
    from rest_framework.test import APIClient
    from apps.payments.models import Payment
    makerspace, actor, applicant, plan, _ = _setup(paid=True)
    set_mode(makerspace, "membership", OFFLINE)
    membership = _member(makerspace, applicant)
    client = APIClient()
    client.force_authenticate(actor)
    response = client.post(f"/api/v1/admin/memberships/{membership.pk}/terms", {"plan_id": plan.pk}, format="json")
    assert response.status_code == 201, response.data
    [payment] = charges(makerspace, SUBJECT)
    assert payment.status == Payment.Status.PENDING and payment.subject_id == response.data["id"]
    from apps.makerspaces.models import MembershipTerm
    cancel_term(actor, MembershipTerm.objects.get(pk=response.data["id"]))
    payment.refresh_from_db()
    assert payment.status == Payment.Status.CANCELED
