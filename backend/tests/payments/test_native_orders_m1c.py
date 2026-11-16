"""Phase 1c: persist native Orders and recover remote creates without duplication."""

import io
import json
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest

from apps.audit.models import AuditLog
from apps.payments import services_mobile_razorpay
from apps.payments.models import Payment
from apps.payments.providers.razorpay import RazorpayProvider
from apps.payments.services_mobile import create_mobile_intent
from tests.payments.test_mobile_intent_vendor import _razorpay_debt
from tests.payments.test_mobile_payments import device_client
from tests.payments.test_mobile_razorpay_orders import order_for

pytestmark = pytest.mark.django_db


def mobile_url(space, payment):
    return f"/api/v1/member/makerspaces/{space.pk}/payments/{payment.pk}/mobile-intent"


def order_audits(payment):
    return AuditLog.objects.filter(
        makerspace=payment.makerspace, target_type="payments.payment",
        target_id=str(payment.pk), action="payment.mobile_order_created",
    )


@pytest.mark.parametrize("claimed", [True, False])
def test_native_order_created_once_stored_and_reused(monkeypatch, claimed):
    space, member, payment = _razorpay_debt("m1c-order-once", claimed=claimed)
    calls = []
    order = order_for(payment)

    def request(self, source, method, path, body=None):
        calls.append((method, path, body))
        assert source.vendor == "razorpay"
        if path.startswith("/orders?"):
            assert parse_qs(urlsplit(path).query)["receipt"] == [order["receipt"]]
            return {"items": []}
        if method == "POST":
            assert path == "/orders"
            assert body == {
                **{key: order[key] for key in ("amount", "currency", "receipt", "notes")},
                "payment_capture": 1,  # PAY-REVIEW 0.12.0: automatic capture is requested
            }
            assert len(body["receipt"]) <= 40
        else:
            assert (method, path) == ("GET", "/orders/order_mobile")
        return order

    monkeypatch.setattr(RazorpayProvider, "_request", request)
    client = device_client(member, space)
    first = client.post(mobile_url(space, payment), format="json")
    second = client.post(mobile_url(space, payment), format="json")

    assert first.status_code == second.status_code == 200
    assert first.data == second.data
    assert [(method, path.split("?")[0]) for method, path, _ in calls] == [
        ("GET", "/orders"), ("POST", "/orders"), ("GET", "/orders/order_mobile"),
    ]
    payment.refresh_from_db()
    assert payment.provider == Payment.Provider.RAZORPAY
    assert payment.external_order_id == "order_mobile"
    assert payment.online_rail == Payment.OnlineRail.NATIVE_PAYMENT_INTENT
    assert payment.stripe_payment_intent_id is None
    assert payment.checkout_url == ""
    assert order_audits(payment).count() == 1
    assert order_audits(payment).get().meta == {
        "provider": "razorpay", "order_id": "order_mobile",
    }


def test_remote_create_survives_local_rollback_and_recovers_exact_receipt(monkeypatch):
    space, member, payment = _razorpay_debt("m1c-order-rollback", claimed=False)
    before = Payment.objects.filter(pk=payment.pk).values().get()
    remote, creates = [], []

    def request(self, source, method, path, body=None):
        if method == "GET":
            assert path.startswith("/orders?")
            return {"items": list(remote)}
        assert (method, path) == ("POST", "/orders")
        creates.append(body)
        remote.append(order_for(payment))
        return remote[-1]

    monkeypatch.setattr(RazorpayProvider, "_request", request)
    record = services_mobile_razorpay.audit.record

    def fail_order_audit(actor, action, **kwargs):
        if action == "payment.mobile_order_created":
            raise RuntimeError("local transaction lost after remote create")
        return record(actor, action, **kwargs)

    with monkeypatch.context() as local:
        local.setattr(services_mobile_razorpay.audit, "record", fail_order_audit)
        with pytest.raises(RuntimeError, match="local transaction lost"):
            create_mobile_intent(payment.pk, actor=member)

    assert Payment.objects.filter(pk=payment.pk).values().get() == before
    assert not order_audits(payment).exists()
    # Substring results must not displace the exact receipt during recovery.
    remote.insert(0, order_for(payment, id="order_partial", receipt=f"sw-pay-{payment.pk}0"))
    result = create_mobile_intent(payment.pk, actor=member)

    payment.refresh_from_db()
    assert len(creates) == 1
    assert result["order_id"] == payment.external_order_id == "order_mobile"
    assert payment.online_rail == Payment.OnlineRail.NATIVE_PAYMENT_INTENT
    assert payment.provider == Payment.Provider.RAZORPAY
    assert order_audits(payment).count() == 1


def test_duplicate_receipt_http_400_recovered_by_second_lookup(monkeypatch):
    space, member, payment = _razorpay_debt("m1c-order-duplicate", claimed=True)
    calls = []

    def urlopen(request, timeout):
        method, path = request.get_method(), urlsplit(request.full_url).path
        calls.append((method, path))
        assert timeout > 0
        if method == "POST":
            assert path == "/v1/orders"
            assert json.loads(request.data)["receipt"] == f"sw-pay-{payment.pk}"
            error = {"error": {
                "code": "BAD_REQUEST_ERROR", "description": "Receipt must be unique",
            }}
            raise HTTPError(
                request.full_url, 400, "Bad Request", {},
                io.BytesIO(json.dumps(error).encode()),
            )
        assert parse_qs(urlsplit(request.full_url).query)["receipt"] == [f"sw-pay-{payment.pk}"]
        items = [] if len(calls) == 1 else [order_for(payment, status="attempted")]
        return io.BytesIO(json.dumps({"items": items}).encode())

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    response = device_client(member, space).post(mobile_url(space, payment), format="json")

    assert response.status_code == 200
    assert calls == [("GET", "/v1/orders"), ("POST", "/v1/orders"), ("GET", "/v1/orders")]
    payment.refresh_from_db()
    assert response.data["order_id"] == payment.external_order_id == "order_mobile"
    assert payment.online_rail == Payment.OnlineRail.NATIVE_PAYMENT_INTENT
    assert order_audits(payment).count() == 1


@pytest.mark.parametrize("failure", ["partial_receipt", "amount", "currency"])
@pytest.mark.parametrize("stored", [False, True])
def test_incompatible_native_order_returns_503_without_writes(monkeypatch, failure, stored):
    space, member, payment = _razorpay_debt("m1c-order-mismatch", claimed=True)
    if stored:
        payment.external_order_id = "order_mobile"
        payment.online_rail = Payment.OnlineRail.NATIVE_PAYMENT_INTENT
        payment.save()
    before = Payment.objects.filter(pk=payment.pk).values().get()
    changes = {
        "partial_receipt": {"receipt": f"sw-pay-{payment.pk}0"},
        "amount": {"amount": 1251}, "currency": {"currency": "USD"},
    }[failure]
    calls = []

    def request(self, source, method, path, body=None):
        calls.append((method, path))
        assert method == "GET", "An incompatible order must never cause a new create"
        order = order_for(payment, **changes)
        return order if stored else {"items": [order]}

    monkeypatch.setattr(RazorpayProvider, "_request", request)
    response = device_client(member, space).post(mobile_url(space, payment), format="json")

    assert response.status_code == 503
    assert response.data == {
        "detail": "Payments are temporarily unavailable.", "code": "payments_unavailable",
    }
    assert len(calls) == 1
    assert Payment.objects.filter(pk=payment.pk).values().get() == before
    assert not order_audits(payment).exists()


def test_hosted_payment_link_conflicts_before_any_native_provider_call(monkeypatch):
    space, member, payment = _razorpay_debt("m1c-order-link", claimed=True)
    payment.online_rail = Payment.OnlineRail.CHECKOUT
    payment.external_order_id = "plink_existing"
    payment.checkout_url = "https://rzp.io/i/existing"
    payment.save()
    before = Payment.objects.filter(pk=payment.pk).values().get()
    calls = []
    monkeypatch.setattr(
        RazorpayProvider, "_request",
        lambda *args, **kwargs: calls.append((args, kwargs)) or {},
    )

    response = device_client(member, space).post(mobile_url(space, payment), format="json")

    assert response.status_code == 409
    assert response.data["code"] == "payment_rail_conflict"
    assert calls == []
    assert Payment.objects.filter(pk=payment.pk).values().get() == before
    assert not order_audits(payment).exists()
