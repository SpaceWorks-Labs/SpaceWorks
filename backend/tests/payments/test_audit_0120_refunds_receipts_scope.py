"""Payments audit 0.12.0, sub-lane C: refunds, receipts and money-view scope (decision 256).

C-1 an unknown provider outcome never frees the balance (no double refund on retry);
C-2 refund amounts respect the currency exponent (JPY 0, KWD 3 stored at two places);
C-3/C-4 an area owner releases a closed loan's cash deposit and corrects its receipt (242(c));
C-5 a refunded gift's tax receipt states the money returned and the net;
C-6 area owners read their own area's payment documents, never another area's or gifts.
"""

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.hardware_requests.models import HardwareRequest
from apps.payments.exceptions_refunds import RefundNotAllowed
from apps.payments.models import Payment, PaymentDocument, Refund
from apps.payments.reconciliation import mark_offline
from apps.payments.services import apply_webhook_event
from apps.payments.services_refunds import outcome_unknown
from apps.payments.services_refunds_offline import amend_offline_refund, record_offline_refund
from apps.payments.providers import PaymentsUnavailable
from tests.payments.test_refunds import FakeStripe, paid_deposit, refund_url, stripe_space
from tests.rbac_f6_helpers import custom_actor
from tests.return_helpers import authenticated_client, make_member, make_space, settlement_details

pytestmark = pytest.mark.django_db


class _StripeHttpError(Exception):
    def __init__(self, status):
        super().__init__(f"stripe {status}")
        self.http_status = status


class APIConnectionError(Exception):
    """Named like the Stripe SDK's network error, which carries no HTTP status."""


def _wrapped(cause):
    try:
        raise PaymentsUnavailable("Stripe rejected the refund.") from cause
    except PaymentsUnavailable as exc:
        return exc


def _receipt(**extra):
    return {"method": "cash", "reference": "slip-1", "refunded_at": timezone.now(), **extra}


def _cash_payment(space, staff, *, currency="usd", amount="10.00"):
    payment = paid_deposit(space, staff, status=Payment.Status.PENDING, amount=amount, intent=f"pi_c_{space.slug}")
    if currency != "usd":
        Payment.objects.filter(pk=payment.pk).update(currency=currency)
        payment.refresh_from_db()
    mark_offline(payment, staff, settlement_details())
    payment.refresh_from_db()
    return payment


# ---- C-1: unknown outcome ---------------------------------------------------------------

@pytest.mark.parametrize("cause, unknown", [
    (TimeoutError("read timed out"), True),
    (ConnectionError("reset by peer"), True),
    (APIConnectionError("no route"), True),
    (_StripeHttpError(502), True),
    (_StripeHttpError(400), False),
    (_StripeHttpError(402), False),
    (RuntimeError("stripe down"), False),
])
def test_outcome_classifier(cause, unknown):
    assert outcome_unknown(_wrapped(cause)) is unknown


def test_razorpay_status_is_read_from_its_request_error():
    from apps.payments.providers.razorpay import RazorpayRequestError

    assert outcome_unknown(RazorpayRequestError(400, "BAD_REQUEST_ERROR", "x")) is False
    assert outcome_unknown(RazorpayRequestError(503)) is True
    assert outcome_unknown(PaymentsUnavailable("not configured")) is False


def test_timeout_keeps_the_refund_pending_and_the_balance_reserved(monkeypatch):
    space, staff = stripe_space("c1-timeout", monkeypatch, [TimeoutError("read timed out"),
                                                             {"id": "re_second", "status": "succeeded"}])
    payment = paid_deposit(space, staff, intent="pi_c1")
    client = authenticated_client(staff)

    first = client.post(refund_url(payment), {"amount": "10.00"}, format="json")
    assert first.status_code == 200
    refund = Refund.objects.get(payment=payment)
    assert refund.status == Refund.Status.PENDING and refund.external_refund_id is None
    assert AuditLog.objects.filter(action="payment.refund_requested", meta__outcome_unknown=True).count() == 1
    assert not AuditLog.objects.filter(action="payment.refund_failed").exists()

    # The retry that used to raise a second provider refund is refused: the money is reserved.
    retry = client.post(refund_url(payment), {"amount": "10.00"}, format="json")
    assert retry.status_code == 400 and retry.data["code"] == "refund_exceeds_balance"
    assert len(FakeStripe.calls) == 1

    # The provider's webhook for the refund it did make binds and settles the reserved row once.
    event = {"id": "evt_c1", "type": "charge.refunded", "data": {"object": {
        "id": "ch_c1", "payment_intent": "pi_c1",
        "refunds": {"data": [{"id": "re_first", "status": "succeeded", "amount": 1000}]}}}}
    apply_webhook_event(space, event)
    apply_webhook_event(space, event)
    refund.refresh_from_db()
    assert (refund.status, refund.external_refund_id) == (Refund.Status.SUCCEEDED, "re_first")
    assert Refund.objects.filter(payment=payment).count() == 1
    assert AuditLog.objects.filter(action="payment.refunded").count() == 1


def test_a_definitive_refusal_still_frees_the_balance(monkeypatch):
    space, staff = stripe_space("c1-refused", monkeypatch, [_StripeHttpError(400),
                                                            {"id": "re_ok", "status": "succeeded"}])
    payment = paid_deposit(space, staff, intent="pi_c1r")
    client = authenticated_client(staff)
    assert client.post(refund_url(payment), {"amount": "10.00"}, format="json").status_code == 502
    assert Refund.objects.get(payment=payment).status == Refund.Status.FAILED
    assert client.post(refund_url(payment), {"amount": "10.00"}, format="json").status_code == 200


def test_sequential_partial_refunds_cannot_exceed_the_charge(monkeypatch):
    space, staff = stripe_space("c1-double", monkeypatch, [{"id": "re_a", "status": "pending"},
                                                           {"id": "re_b", "status": "pending"}])
    payment = paid_deposit(space, staff, intent="pi_c1d")
    client = authenticated_client(staff)
    assert client.post(refund_url(payment), {"amount": "6.00"}, format="json").status_code == 200
    second = client.post(refund_url(payment), {"amount": "6.00"}, format="json")
    assert second.status_code == 400 and second.data["code"] == "refund_exceeds_balance"
    assert Refund.counted_total(payment) == Decimal("6.00") and len(FakeStripe.calls) == 1


# ---- C-2: currency exponents --------------------------------------------------------------

def test_jpy_online_refund_must_be_whole_yen_and_is_sent_unscaled(monkeypatch):
    space, staff = stripe_space("c2-jpy", monkeypatch, [{"id": "re_jpy", "status": "succeeded"}])
    payment = paid_deposit(space, staff, amount="1000.00", intent="pi_jpy")
    Payment.objects.filter(pk=payment.pk).update(currency="jpy")
    client = authenticated_client(staff)

    half = client.post(refund_url(payment), {"amount": "0.50"}, format="json")
    assert half.status_code == 400 and half.data["code"] == "refund_amount_invalid"
    assert not FakeStripe.calls and not Refund.objects.filter(payment=payment).exists()

    assert client.post(refund_url(payment), {"amount": "300"}, format="json").status_code == 200
    assert FakeStripe.calls[0][0]["amount"] == 300


def test_kwd_refund_is_sent_in_fils(monkeypatch):
    space, staff = stripe_space("c2-kwd", monkeypatch, [{"id": "re_kwd", "status": "succeeded"}])
    payment = paid_deposit(space, staff, amount="5.00", intent="pi_kwd")
    Payment.objects.filter(pk=payment.pk).update(currency="kwd")
    assert authenticated_client(staff).post(refund_url(payment), {"amount": "1.25"}, format="json").status_code == 200
    assert FakeStripe.calls[0][0]["amount"] == 1250


def test_jpy_cash_refund_refuses_a_fraction_of_a_yen():
    space = make_space("c2-jpy-cash")
    staff = make_member("c2-jpy-cash-staff", space)
    payment = _cash_payment(space, staff, currency="jpy", amount="1000.00")
    with pytest.raises(RefundNotAllowed) as refused:
        record_offline_refund(payment, amount="10.50", reason="r", receipt=_receipt(), actor=staff)
    assert refused.value.detail["code"] == "refund_amount_invalid"
    refund = record_offline_refund(payment, amount="10", reason="r", receipt=_receipt(), actor=staff)
    assert refund.amount == Decimal("10.00")


# ---- C-3 / C-4: area owners and cash deposits ---------------------------------------------

def _closed_deposit(slug):
    space = make_space(slug)
    staff = make_member(f"{slug}-sm", space)
    payment = _cash_payment(space, staff)
    HardwareRequest.objects.filter(pk=payment.subject_id).update(status=HardwareRequest.Status.RETURNED)
    return space, staff, payment


def test_inventory_owner_releases_a_closed_loans_cash_deposit():
    space, _staff, payment = _closed_deposit("c3-release")
    inventory = custom_actor(space, ["issue_request", "return_request", "edit_inventory"], name="inv")
    url = reverse("payment-deposit-release", args=[space.pk, payment.pk])
    response = authenticated_client(inventory).post(url, {
        "amount": "10.00", "reason": "Deposit released",
        "receipt": {"method": "cash", "reference": "slip-1", "refunded_at": timezone.now().isoformat()},
    }, format="json")
    assert response.status_code == 200, response.content
    refund = Refund.objects.get(payment=payment)
    assert refund.created_by == inventory and refund.provider == Refund.Provider.MANUAL
    assert AuditLog.objects.filter(action="payment.refund_recorded", actor=inventory).exists()


def test_deposit_release_still_waits_for_the_loan_to_close():
    space = make_space("c3-open")
    staff = make_member("c3-open-sm", space)
    payment = _cash_payment(space, staff)
    inventory = custom_actor(space, ["issue_request", "return_request"], name="inv")
    with pytest.raises(RefundNotAllowed) as refused:
        record_offline_refund(payment, amount="10.00", reason="r", receipt=_receipt(), actor=inventory,
                              release_deposit=True)
    assert refused.value.detail["code"] == "deposit_not_returned"


def test_area_owner_corrects_their_cash_refund_receipt_and_strangers_cannot():
    space, _staff, payment = _closed_deposit("c4-amend")
    inventory = custom_actor(space, ["issue_request", "return_request"], name="inv")
    refund = record_offline_refund(payment, amount="4.00", reason="r", receipt=_receipt(), actor=inventory)
    replacement = amend_offline_refund(payment, refund_id=refund.pk, actor=inventory,
                                       receipt={"method": "bank_transfer", "reference": "corrected",
                                                "refunded_at": timezone.now().isoformat()})
    assert replacement.amends_id == refund.pk and replacement.amount == refund.amount
    assert Refund.counted_total(payment) == Decimal("4.00")

    events = custom_actor(space, ["manage_events"], name="events")
    from rest_framework.exceptions import NotFound
    with pytest.raises(NotFound):
        amend_offline_refund(payment, refund_id=replacement.pk, actor=events,
                             receipt={"method": "cash", "reference": "", "refunded_at": timezone.now().isoformat()})


# ---- C-5: tax receipt after a refund ------------------------------------------------------

@pytest.mark.django_db(transaction=True)
def test_refunded_gift_tax_receipt_states_the_return_and_the_net(monkeypatch, django_capture_on_commit_callbacks):
    from apps.operations import printable_pdf
    from apps.payments.donations.tax_receipt_pdf import render_tax_receipt, returned_amount
    from tests.l18_local.helpers import charge_for, gift, settle_offline, setup
    from tests.l18_local.test_nonprofit_242m import profile

    space, manager, donor = setup("c5-gift")
    profile(space)
    donation, _ = gift(space, donor, amount="250", wants_tax_receipt=True)
    payment = charge_for(donation)
    with django_capture_on_commit_callbacks(execute=True):
        settle_offline(manager, payment)
    payment.refresh_from_db()
    donation.refresh_from_db()
    assert donation.tax_receipt and returned_amount(donation) == Decimal("0.00")

    now = timezone.now()
    Refund.objects.create(payment=payment, amount=Decimal("100.00"), currency=payment.currency,
                          status=Refund.Status.SUCCEEDED, provider=Refund.Provider.MANUAL, method="cash",
                          refunded_at=now, settled_at=now, created_by=manager)
    assert returned_amount(donation) == Decimal("100.00")

    seen = []
    original = printable_pdf.document_paragraph

    def capture(value, *args, **kwargs):
        seen.append(str(value))
        return original(value, *args, **kwargs)

    monkeypatch.setattr(printable_pdf, "document_paragraph", capture)
    assert render_tax_receipt(donation).startswith(b"%PDF")
    assert "Returned to donor" in seen and "Net donation" in seen
    currency = donation.currency.upper()
    assert f"{currency} 100.00" in seen and f"{currency} 150.00" in seen


# ---- C-6: document scope ------------------------------------------------------------------

def test_area_owner_reads_own_area_documents_but_not_other_areas():
    space = make_space("c6-docs")
    staff = make_member("c6-docs-sm", space)
    payment = _cash_payment(space, staff)
    space.enabled_features = list({*(space.enabled_features or []), "billing.documents"})
    space.save(update_fields=["enabled_features", "updated_at"])
    document = PaymentDocument.objects.filter(payment=payment).first()
    if document is None:
        from apps.payments.documents import issue_receipt
        document = issue_receipt(payment, actor=staff)
    assert document is not None
    url = reverse("staff-payment-documents", args=[space.pk])
    grant = reverse("staff-payment-document-url", args=[space.pk, document.pk])

    inventory = custom_actor(space, ["issue_request"], name="inv")
    listed = authenticated_client(inventory).get(url)
    assert listed.status_code == 200 and [row["id"] for row in listed.data["results"]] == [document.pk]
    assert authenticated_client(inventory).get(grant).status_code == 200

    events = custom_actor(space, ["manage_events"], name="events")
    assert authenticated_client(events).get(url).data["count"] == 0
    assert authenticated_client(events).get(grant).status_code == 404

    nobody = custom_actor(space, ["manage_bookings"], name="stock")  # edit_inventory = Inventory Manager = loans owner
    assert authenticated_client(nobody).get(grant).status_code == 404


def test_gift_documents_never_reach_an_area_manager():
    from apps.payments.area_queue import area_payments

    space = make_space("c6-gifts")
    staff = make_member("c6-gifts-sm", space)
    payment = _cash_payment(space, staff)
    Payment.objects.filter(pk=payment.pk).update(subject_type=Payment.SubjectType.DONATION)
    manager = custom_actor(space, ["issue_request", "return_request", "manage_events", "manage_bookings",
                                   "manage_shop"], name="areas")
    assert not area_payments(manager, space.pk).filter(pk=payment.pk).exists()
