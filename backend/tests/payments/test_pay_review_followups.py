"""PAY-REVIEW 0.12.0 follow-ups (decision 360): fee rounding, capture, unknown refunds, paid
status, replayed Razorpay bodies."""

import json
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.payments.checkout_provider import _application_fee_amount
from apps.payments.models import Payment, Refund
from apps.payments.providers.razorpay import RazorpayProvider, RazorpayUnreadableResponse
from apps.payments.services_refunds import outcome_unknown, refund_payment
from apps.payments.services_webhooks import apply_webhook_event
from tests.payments.recon_f_helpers import pending_charge
from tests.payments.test_razorpay_provider import configure_razorpay, sign
from tests.payments.test_razorpay_refund_sync import _paid_razorpay_deposit

pytestmark = pytest.mark.django_db


# --- Connect fee: three-decimal currencies move in 10-fils steps ------------------------

@pytest.mark.parametrize(("amount", "bps", "currency", "fee"), [
    ("12.340", 250, "kwd", 310),  # 308.5 fils -> 310, never a stray fils Stripe refuses
    ("1.000", 125, "bhd", 10),    # 12.5 fils -> 10
    ("12.34", 250, "usd", 31),    # two-decimal currencies are unchanged
    ("1500", 1000, "jpy", 150),
])
def test_connect_fee_is_capturable_in_every_currency(amount, bps, currency, fee):
    assert _application_fee_amount(Decimal(amount), bps, currency) == fee


# --- Razorpay native Orders ask for automatic capture -----------------------------------

def test_a_native_order_requests_automatic_capture(monkeypatch):
    sent = {}

    def request(self, source, method, path, body=None, *, idempotency_key=None):
        sent.update(body or {})
        return {"id": "order_cap"}

    monkeypatch.setattr(RazorpayProvider, "_request", request)
    RazorpayProvider().create_order(object(), amount_minor=1000, currency="inr", receipt="sw-pay-1", notes={})
    assert sent["payment_capture"] == 1


# --- An unreadable refund answer is an unknown outcome, never a refusal ------------------

class _Unreadable:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return b"<html>gateway hiccup</html>"


def test_unreadable_refund_answer_keeps_the_refund_pending_and_reserved(monkeypatch):
    _space, staff, payment = _paid_razorpay_deposit("prv-unreadable", external_id="pay_prv_unreadable")
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: _Unreadable())
    refund = refund_payment(payment, amount="100.00", reason="", actor=staff)
    refund.refresh_from_db()
    assert refund.status == Refund.Status.PENDING and refund.external_refund_id is None
    assert Refund.counted_total(Payment.objects.get(pk=payment.pk)) == Decimal("100.00")
    assert AuditLog.objects.filter(action="payment.refund_requested", meta__outcome_unknown=True).count() == 1
    assert not AuditLog.objects.filter(action="payment.refund_failed").exists()


def test_an_exception_carrying_a_2xx_is_an_unknown_outcome():
    class StripeApiError(Exception):
        http_status = 200

    assert outcome_unknown(RazorpayUnreadableResponse()) is True
    assert outcome_unknown(StripeApiError("Invalid response body from API")) is True


# --- A Stripe checkout is paid only when it says "paid" ---------------------------------

@pytest.mark.parametrize("payment_status", [None, "no_payment_required", "unpaid"])
def test_completed_checkout_without_paid_status_never_settles(payment_status):
    space, _staff, payment = pending_charge(f"prv-status-{str(payment_status).lower().replace('_', '-')}", stripe_checkout_session_id="cs_prv")
    obj = {"id": "cs_prv", "payment_intent": "pi_prv"}
    if payment_status is not None:
        obj["payment_status"] = payment_status
    assert apply_webhook_event(space, {"id": "evt_prv", "type": "checkout.session.completed",
                                       "data": {"object": obj}}) is None
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PENDING


def test_completed_checkout_marked_paid_settles():
    space, _staff, payment = pending_charge("prv-status-paid", stripe_checkout_session_id="cs_prv_paid")
    apply_webhook_event(space, {"id": "evt_prv_paid", "type": "checkout.session.completed", "data": {
        "object": {"id": "cs_prv_paid", "payment_status": "paid", "payment_intent": "pi_prv_paid"}}})
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PAID_ONLINE


# --- A replayed Razorpay body under a fresh delivery id is a duplicate -------------------

def _failure_body(payment_id):
    return json.dumps({"event": "payment.failed", "payload": {
        "payment": {"entity": {"id": payment_id, "order_id": "order_prv_replay"}}}}).encode()


def _post(space, body, event_id):
    return APIClient().post(reverse("razorpay-webhook", args=[space.public_code]), data=body,
                            content_type="application/json", HTTP_X_RAZORPAY_SIGNATURE=sign(body),
                            HTTP_X_RAZORPAY_EVENT_ID=event_id)


def test_a_replayed_razorpay_body_with_a_new_delivery_id_is_ignored():
    space, _staff, payment = pending_charge("prv-replay", provider="razorpay", online_rail="native_payment_intent",
                                            external_order_id="order_prv_replay")
    configure_razorpay(space)
    failures = AuditLog.objects.filter(action="payment.failed", target_id=str(payment.pk))
    assert _post(space, _failure_body("pay_prv_1"), "evt_prv_a").status_code == 200
    assert _post(space, _failure_body("pay_prv_1"), "evt_prv_b").status_code == 200  # same signed body
    assert failures.count() == 1
    assert _post(space, _failure_body("pay_prv_2"), "evt_prv_c").status_code == 200  # a genuine second attempt
    assert failures.count() == 2
