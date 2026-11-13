"""Staff decisions: approval is the only path to money; every rule is enforced under lock."""

from decimal import Decimal

import pytest

from apps.accounts import rbac
from apps.audit.models import AuditLog
from apps.payments.models import Payment, Refund, RefundCase
from apps.payments.services_refund_cases import open_due_case
from apps.payments.services_refunds_offline import record_offline_refund
from tests.payments.refund_case_helpers import (
    base, charge, finance_reader, member, paid_event, receipt, receipt_payload, registration, space_with_currency,
)
from tests.payments.test_refunds import FakeStripe, stripe_space
from tests.rbac_f6_helpers import custom_actor
from tests.return_helpers import authenticated_client, make_member, make_space

pytestmark = pytest.mark.django_db


def due_case(space, slug, status="paid_offline", **extra):
    user = member(f"{slug}-m", space)
    payment = charge(space, user, subject_id=registration(paid_event(space), user).pk, status=status, **extra)
    return open_due_case(payment, reason_code="event_cancelled", actor=None)


def approve(actor, case, body):
    return authenticated_client(actor).post(f"{base(case.payment.makerspace)}/refund-cases/{case.pk}/approve",
                                            body, format="json")


def test_offline_approval_needs_a_receipt_and_records_a_manual_refund():
    space = space_with_currency("dec-offline")
    staff = make_member("dec-offline-staff", space)
    case = due_case(space, "dec-offline")
    missing = approve(staff, case, {})
    assert missing.status_code == 400 and missing.data["code"] == "refund_receipt_required"
    assert not Refund.objects.exists() and RefundCase.objects.get(pk=case.pk).status == "open"
    response = approve(staff, case, {"amount": "12.00", "note": "Event off", "receipt": receipt_payload()})
    assert response.status_code == 200, response.data
    assert response.data["status"] == "approved" and response.data["refund"]["provider"] == "manual"
    refund = Refund.objects.get()
    assert (refund.amount, refund.method, refund.reference) == (Decimal("12.00"), "cash", "slip-1")
    assert AuditLog.objects.filter(action="payment.refund_case_approved", meta__refund_id=refund.pk).exists()
    again = approve(staff, case, {"receipt": receipt_payload()})
    assert again.status_code == 409 and again.data["code"] == "refund_case_closed"


def test_online_approval_sends_after_commit_and_a_refusal_can_be_retried(monkeypatch,
                                                                        django_capture_on_commit_callbacks):
    space, staff = stripe_space("dec-online", monkeypatch, [RuntimeError("card network down"),
                                                          {"id": "re_ok", "status": "succeeded"}])
    case = due_case(space, "dec-online", status="paid_online", provider="stripe",
                    stripe_payment_intent_id="pi_dec")
    # The provider call runs after commit; in production that is before the view re-reads
    # the case, here the test transaction defers it to the end of the capture block.
    with django_capture_on_commit_callbacks(execute=True):
        assert approve(staff, case, {}).status_code == 200
    assert RefundCase.objects.get(pk=case.pk).status == "approval_failed"
    assert Refund.objects.get().status == "failed"
    with django_capture_on_commit_callbacks(execute=True):
        assert approve(staff, case, {"amount": "20.00"}).status_code == 200
    retried = RefundCase.objects.select_related("refund").get(pk=case.pk)
    assert retried.status == "approved" and retried.refund.status == "succeeded"
    assert len(FakeStripe.calls) == 2 and FakeStripe.calls[1][0]["amount"] == 2000


def test_amount_over_balance_and_exhausted_balance_conflict():
    space = space_with_currency("dec-balance")
    staff = make_member("dec-balance-staff", space)
    case = due_case(space, "dec-balance")
    over = approve(staff, case, {"amount": "20.01", "receipt": receipt_payload()})
    assert over.status_code == 409 and over.data["code"] == "refund_exceeds_balance"
    bad = approve(staff, case, {"amount": "0.001", "receipt": receipt_payload()})
    assert bad.status_code == 400
    # A staff refund straight from the ledger empties the charge: the case is voided (R7).
    record_offline_refund(case.payment, amount=Decimal("20.00"), reason="desk", receipt=receipt(), actor=staff)
    assert RefundCase.objects.get(pk=case.pk).status == "void"
    assert approve(staff, case, {"receipt": receipt_payload()}).data["code"] == "refund_case_closed"


def test_partial_refund_outside_the_case_is_reclamped_on_approval():
    space = space_with_currency("dec-reclamp")
    staff = make_member("dec-reclamp-staff", space)
    case = due_case(space, "dec-reclamp")
    record_offline_refund(case.payment, amount=Decimal("15.00"), reason="desk", receipt=receipt(), actor=staff)
    response = approve(staff, case, {"receipt": receipt_payload()})
    assert response.status_code == 200 and Decimal(response.data["approved_amount"]) == Decimal("5.00")


def test_rail_removed_online_case_can_only_be_declined(monkeypatch):
    space = space_with_currency("dec-rail")
    staff = make_member("dec-rail-staff", space)
    case = due_case(space, "dec-rail", status="paid_online", provider="stripe", stripe_payment_intent_id="pi_r")
    monkeypatch.setattr("apps.separability.tombstones.app_is_tombstoned", lambda label: label == "payments_rail")
    blocked = approve(staff, case, {})
    assert blocked.status_code == 409 and blocked.data["code"] == "refund_rail_unavailable"
    declined = authenticated_client(staff).post(f"{base(space)}/refund-cases/{case.pk}/decline",
                                                {"note": "Refund by bank transfer later"}, format="json")
    assert declined.status_code == 200 and declined.data["status"] == "declined"
    assert declined.data["decision_note"] == "Refund by bank transfer later" and not Refund.objects.exists()


def test_finance_reads_but_cannot_decide_and_other_tenants_see_nothing():
    space = space_with_currency("dec-scope")
    case = due_case(space, "dec-scope")
    finance = finance_reader(space)
    events = custom_actor(space, [rbac.Action.MANAGE_EVENTS], name="events")
    bookings = custom_actor(space, [rbac.Action.MANAGE_BOOKINGS], name="bookings")
    foreign = make_member("dec-scope-foreign", make_space("dec-scope-other"))
    queue = f"{base(space)}/refund-cases"
    assert authenticated_client(finance).get(queue).data["count"] == 1
    assert approve(finance, case, {"receipt": receipt_payload()}).status_code == 403
    assert authenticated_client(events).get(queue).data["count"] == 1
    assert authenticated_client(bookings).get(queue).data["count"] == 0
    assert authenticated_client(bookings).get(f"{queue}/{case.pk}").status_code == 404
    assert authenticated_client(foreign).get(queue).status_code == 404
    assert approve(foreign, case, {"receipt": receipt_payload()}).status_code == 404
    # Decisions 217/242: the charge's subject owner (the Event Manager, for an event charge) records and
    # decides its cash refund; finance staff and unrelated areas still cannot (asserted above).
    assert approve(events, case, {"receipt": receipt_payload()}).status_code == 200
    assert Refund.objects.count() == 1


def test_queue_filters_and_one_active_case_per_payment():
    space = space_with_currency("dec-filter")
    staff = make_member("dec-filter-staff", space)
    case = due_case(space, "dec-filter")
    client = authenticated_client(staff)
    assert client.get(f"{base(space)}/refund-cases?status=open&area=events&kind=due").data["count"] == 1
    assert client.get(f"{base(space)}/refund-cases?status=declined").data["count"] == 0
    assert client.get(f"{base(space)}/refund-cases?status=bogus").status_code == 400
    from django.db import IntegrityError, transaction
    with pytest.raises(IntegrityError), transaction.atomic():
        RefundCase.objects.create(payment=case.payment, kind="request", area="events", reason_code="member_request")
    assert Payment.objects.get(pk=case.payment_id).status == "paid_offline"


def test_a_late_provider_failure_returns_the_case_to_staff(monkeypatch, django_capture_on_commit_callbacks):
    from apps.payments.services_refunds import settle_refund
    space, staff = stripe_space("dec-webhook", monkeypatch, [{"id": "re_late", "status": "pending"}])
    case = due_case(space, "dec-webhook", status="paid_online", provider="stripe", stripe_payment_intent_id="pi_w")
    with django_capture_on_commit_callbacks(execute=True):
        approve(staff, case, {})
    refund = Refund.objects.get()
    assert refund.status == "pending" and RefundCase.objects.get(pk=case.pk).status == "approved"
    settle_refund(refund, external_refund_id="re_late", status=Refund.Status.FAILED, actor=None)
    assert RefundCase.objects.get(pk=case.pk).status == "approval_failed"
    assert AuditLog.objects.filter(action="payment.refund_case_approval_failed", meta__refund_id=refund.pk).exists()
