"""Phase 1c: vendor-discriminated native responses preserve Stripe PaymentSheet."""

import pytest

from apps.audit.models import AuditLog
from apps.payments import stripe_client
from apps.payments.models import Payment
from apps.payments.providers.razorpay import RazorpayProvider
from tests.payments.account_helpers import make_payer
from tests.payments.test_mobile_intent_vendor import _razorpay_debt
from tests.payments.test_mobile_payments import configured_payment, device_client
from tests.payments.test_mobile_razorpay_orders import order_for
from tests.payments.test_native_orders_m1c import mobile_url
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


def test_razorpay_native_response_has_checkout_parameters_without_secrets(monkeypatch):
    space, member, payment = _razorpay_debt("m1c-contract-razorpay", claimed=True)
    calls, stripe_calls = [], []

    def request(self, source, method, path, body=None):
        calls.append((method, path))
        return {"items": [order_for(payment)]}

    monkeypatch.setattr(RazorpayProvider, "_request", request)
    for method in ("create_payment_intent", "retrieve_payment_intent"):
        monkeypatch.setattr(
            stripe_client, method,
            lambda *args, _method=method, **kwargs: stripe_calls.append(_method),
        )

    response = device_client(member, space).post(mobile_url(space, payment), format="json")

    assert response.status_code == 200
    assert response.data == {
        "vendor": "razorpay", "payment_id": payment.pk, "key_id": "rzp_test_key",
        "order_id": "order_mobile", "amount_minor": 1250, "currency": "INR",
        "name": space.name, "description": "Paid service",
    }
    assert len(calls) == 1
    assert stripe_calls == []
    assert "rzp_test_secret" not in response.content.decode()


def test_stripe_native_response_and_idempotent_intent_creation_unchanged(monkeypatch):
    space = make_space("m1c-contract-stripe")
    member = make_payer("m1c-contract-stripe-member", space)
    payment = configured_payment(space, member)
    creates, retrieves, razorpay_calls = [], [], []
    intent = {"id": "pi_m1c", "client_secret": "pi_m1c_secret"}

    def create(source, *, idempotency_key, **params):
        creates.append((source.vendor, idempotency_key, params))
        return intent

    def retrieve(source, intent_id):
        retrieves.append((source.vendor, intent_id))
        return intent

    monkeypatch.setattr(stripe_client, "create_payment_intent", create)
    monkeypatch.setattr(stripe_client, "retrieve_payment_intent", retrieve)
    monkeypatch.setattr(
        RazorpayProvider, "_request",
        lambda *args, **kwargs: razorpay_calls.append((args, kwargs)) or {},
    )
    client = device_client(member, space)
    first = client.post(mobile_url(space, payment), format="json")
    second = client.post(mobile_url(space, payment), format="json")

    assert first.status_code == second.status_code == 200
    assert first.data == second.data == {
        "vendor": "stripe", "payment_id": payment.pk,
        "publishable_key": "pk_test_mobile", "client_secret": "pi_m1c_secret",
    }
    assert creates == [("stripe", f"payment-mobile-intent-{payment.pk}", {
        "amount": 1250, "currency": "usd", "automatic_payment_methods": {"enabled": True},
        "metadata": {"payment_id": str(payment.pk), "makerspace_id": str(space.pk)},
    })]
    assert retrieves == [("stripe", "pi_m1c")]
    assert razorpay_calls == []
    payment.refresh_from_db()
    assert payment.online_rail == Payment.OnlineRail.NATIVE_PAYMENT_INTENT
    assert payment.stripe_payment_intent_id == "pi_m1c"
    assert payment.external_order_id is None
    assert "pi_m1c_secret" not in str(Payment.objects.filter(pk=payment.pk).values().get())
    assert AuditLog.objects.filter(
        makerspace=space, target_type="payments.payment", target_id=str(payment.pk),
        action="payment.mobile_intent_created",
    ).count() == 1
