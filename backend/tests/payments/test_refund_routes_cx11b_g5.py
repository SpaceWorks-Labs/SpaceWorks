"""Refund queue, policies and manual money-out remain core; exact decisions and receipts."""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.payments.models import Payment, Refund, RefundCase, RefundPolicy
from apps.payments.services_refund_cases import request_refund
from apps.payments.services_refunds_offline import record_offline_refund
from tests.payments.ledger_fixtures_cx11b_g5 import refund_receipt, seed, settled
from tests.payments.route_support_cx11b_g5 import cycle, hidden, ids, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_payments_ledger]
OPS = [("refund-case-list", "GET"), ("refund-case-detail", "GET"), ("refund-case-approve", "POST"),
       ("refund-case-decline", "POST"), ("payment-reconciliation-refund-offline", "POST"),
       ("payment-deposit-release", "POST"), ("payment-refund-amend", "POST")]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["payments", "charges.enabled", "subject_module", "subject_charges"])
@pytest.mark.parametrize("name,method", OPS)
def test_refund_route_exact_money_effect_standing_and_retained_core(native, key, name, method):
    s = seed(native, "loans" if name == "payment-deposit-release" else "membership")
    loan = name == "payment-deposit-release"
    key = {"subject_module": "request_workflow" if loan else "membership",
           "subject_charges": "charges.loans" if loan else "charges.membership"}.get(key, key)
    if name == "payment-deposit-release":
        # Seed an already-returned loan; no workflow transition is exercised by this money route.
        type(s.subject).objects.filter(pk=s.subject.pk).update(status="returned")
    settled(s)
    kwargs, body, audit = {"makerspace_id": s.space.pk}, {}, ()
    case = previous = None
    if name.startswith("refund-case"):
        case = request_refund(s.payment, member=s.payer, reason="G5 request")
        if name != "refund-case-list":
            kwargs["case_id"] = case.pk
        if name.endswith("approve"):
            body = {"amount": "25.00", "receipt": refund_receipt(), "keep_membership": True, "note": "G5 approved"}
            audit = ("payment.refund_recorded", "payment.refund_case_approved")
        elif name.endswith("decline"):
            body, audit = {"note": "G5 declined"}, ("payment.refund_case_declined",)
    else:
        kwargs["payment_id"] = s.payment.pk
        body = {"amount": "25.00", "reason": "G5 returned", "receipt": refund_receipt()}
        audit = ("payment.refund_recorded",)
        if name == "payment-refund-amend":
            previous = record_offline_refund(s.payment, actor=s.actor, amount="25.00", reason="G5 seed", receipt=refund_receipt("G5-OLD"))
            kwargs["refund_id"] = previous.pk
            body, audit = {"receipt": refund_receipt()}, ("payment.refund_amended",)

    def result(response):
        saved = Payment.objects.get(pk=s.payment.pk)
        assert (saved.status, saved.amount) == ("paid_offline", Decimal("100"))
        if name == "refund-case-list":
            assert ids(response) == [case.pk] and response.data["results"][0]["payment"]["id"] == saved.pk
        elif name == "refund-case-detail":
            assert (response.data["id"], response.data["member_reason"], response.data["payment"]["id"]) == (case.pk, "G5 request", saved.pk)
        elif name == "refund-case-decline":
            row = RefundCase.objects.get(pk=case.pk)
            assert (row.status, row.decision_note, row.refund_id) == ("declined", "G5 declined", None)
            assert saved.refunds.count() == 0
        else:
            row = Refund.objects.get(payment=saved, amended_by__isnull=True)
            assert (row.amount, row.currency, row.status, row.provider, row.method, row.reference) == (
                Decimal("25"), "inr", "succeeded", "manual", "cash", "G5-REFUND")
            if case:
                decided = RefundCase.objects.get(pk=case.pk)
                assert (decided.status, decided.approved_amount, decided.refund_id) == ("approved", Decimal("25"), row.pk)
            if previous:
                assert row.amends_id == previous.pk and saved.refunds.count() == 2
                assert Refund.objects.get(pk=previous.pk).reference == "G5-OLD"
            else:
                assert saved.refunds.count() == 1
    w = world(s.space, s.client, reverse(name, kwargs=kwargs), method, body, audit=audit, check=result, probes=[hidden(s.foreign)])
    cycle(w, key)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["payments", "membership"])
@pytest.mark.parametrize("name,method", [("refund-policy-list", "GET"), ("refund-policy-detail", "PUT"),
    ("refund-policy-detail", "DELETE"), ("refund-policy-plan", "PUT"), ("refund-policy-plan", "DELETE")])
def test_refund_policy_route_exact_saved_policy_and_core_independence(native, key, name, method):
    s = seed(native)
    plan = None
    if name == "refund-policy-plan":
        from apps.makerspaces.models import MembershipPlan
        plan = MembershipPlan.objects.create(makerspace=s.space, name="G5 plan", interval="monthly")
    row = RefundPolicy.objects.create(makerspace=s.space, area="membership", plan=plan, full_within_days=3)
    kwargs = {"makerspace_id": s.space.pk}
    if name == "refund-policy-plan":
        kwargs["plan_id"] = plan.pk
    elif name == "refund-policy-detail":
        kwargs["area"] = "membership"
    body = {"full_within_days": 7, "partial_percent": 50, "cancellation_fee": "2.00"} if method == "PUT" else {}
    def result(response):
        query = RefundPolicy.objects.filter(makerspace=s.space, area="membership", plan=plan)
        if method == "DELETE":
            assert query.count() == 0
        elif method == "PUT":
            saved = query.get()
            assert (saved.full_within_days, saved.partial_percent, saved.cancellation_fee) == (7, 50, Decimal("2"))
            assert response.data["configured"] is True and response.data["full_within_days"] == 7
        else:
            assert [(r["area"], r["configured"], r["full_within_days"]) for r in response.data] == [
                ("events", False, 0), ("bookings", False, 0), ("membership", True, 3)]
    w = world(s.space, s.client, reverse(name, kwargs=kwargs), method, body,
        on=(204, None) if method == "DELETE" else (200, None),
        audit=() if method == "GET" else ("payment.refund_policy_updated",), check=result, probes=[hidden(s.foreign)])
    cycle(w, key)
