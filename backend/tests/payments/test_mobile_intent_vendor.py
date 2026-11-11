"""Razorpay native Orders must never send the merchant secret to Stripe."""

from decimal import Decimal

import pytest

from apps.payments import stripe_client
from apps.payments.models import Payment
from apps.payments.services import create_payment
from apps.payments.services_mobile import create_mobile_intent
from apps.payments.providers import PaymentsUnavailable
from apps.payments.providers.razorpay import RazorpayProvider
from tests.payments.test_machine_payments import service_request
from tests.payments.test_mobile_payments import device_client
from tests.payments.test_razorpay_provider import configure_razorpay
from tests.payments.account_helpers import make_payer
from tests.return_helpers import enable_online_rail, make_space

pytestmark = pytest.mark.django_db


def _razorpay_debt(slug, *, claimed):
    space = make_space(slug)
    enable_online_rail(space, "machines")
    member = make_payer(f"{slug}-member", space)
    subject = service_request(space, member)
    if claimed:
        configure_razorpay(space)
    payment = create_payment(
        makerspace=space,
        subject_type=Payment.SubjectType.MACHINE_SERVICE_REQUEST,
        subject_id=subject.pk,
        member=member,
        amount=Decimal("12.50"),
        currency="inr",
        created_by=member,
    )
    if not claimed:
        configure_razorpay(space)
    return space, member, payment


def _stripe_must_not_be_called(monkeypatch):
    calls = []
    for name in ("create_payment_intent", "retrieve_payment_intent"):
        monkeypatch.setattr(
            stripe_client, name, lambda *args, _name=name, **kwargs: calls.append(_name)
        )
    return calls


@pytest.mark.parametrize("claimed", [True, False])
def test_razorpay_order_dispatch_and_unclaimed_provider_stamp(monkeypatch, claimed):
    space, member, payment = _razorpay_debt(f"mobile-vendor-{claimed}", claimed=claimed)
    calls = _stripe_must_not_be_called(monkeypatch)
    def request(self, source, method, path, body=None):
        if method == 'GET':
            return {'items': []}
        assert path == '/orders'
        return {'id': 'order_native', 'status': 'created', **body}

    monkeypatch.setattr(RazorpayProvider, '_request', request)
    response = create_mobile_intent(payment.pk, actor=member)

    assert calls == []
    payment.refresh_from_db()
    assert response['vendor'] == 'razorpay'
    assert response['payment_id'] == payment.pk
    assert response['key_id'] == 'rzp_test_key'
    assert response['amount_minor'] == 1250
    assert payment.provider == Payment.Provider.RAZORPAY
    assert payment.online_rail == Payment.OnlineRail.NATIVE_PAYMENT_INTENT
    assert payment.external_order_id == 'order_native'
    assert payment.stripe_payment_intent_id is None


def test_the_native_endpoint_answers_a_sanitized_503_for_a_razorpay_space(monkeypatch):
    space, member, payment = _razorpay_debt("mobile-vendor-http", claimed=True)
    calls = _stripe_must_not_be_called(monkeypatch)
    def unavailable(*args, **kwargs):
        raise PaymentsUnavailable('private provider diagnostic')
    monkeypatch.setattr(RazorpayProvider, '_request', unavailable)

    response = device_client(member, space).post(
        f"/api/v1/member/makerspaces/{space.pk}/payments/{payment.pk}/mobile-intent",
        format="json",
    )

    assert response.status_code == 503
    assert response.data["code"] == "payments_unavailable"
    assert calls == []
