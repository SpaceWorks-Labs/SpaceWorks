"""Read-only provider recovery: exact outcomes, Connect routing, and safe failures."""
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from apps.payments.models import Payment
from apps.payments_rail import provider_poll as poll


def payment(**overrides):
    return NS(**{"pk": 9, "Provider": Payment.Provider, "provider": "stripe", "stripe_checkout_session_id": "",
                 "stripe_payment_intent_id": "", "external_order_id": "", "external_payment_id": "pay_9",
                 **overrides})


@pytest.fixture
def stripe(monkeypatch):
    client = Mock()
    build = Mock(return_value=client)
    monkeypatch.setattr("apps.payments.stripe_client.build_client", build)
    return client


@pytest.mark.parametrize("connect", [False, True])
@pytest.mark.parametrize("paid", [False, True])
def test_hosted_checkout_keeps_processing_intent_and_routes_connect_to_its_account(stripe, connect, paid):
    source = NS(provider="connect" if connect else "raw", connected_account_id="acct_9")
    stripe.v1.checkout.sessions.retrieve.return_value = {
        "payment_status": "paid" if paid else "unpaid", "payment_intent": "pi_9", "amount_total": 1250,
        "currency": "kwd"}
    result = poll.poll_checkout(payment(stripe_checkout_session_id="cs_9"), source)
    assert result == (poll.PolledCapture(True, "pi_9", 1250, "kwd") if paid else poll.PolledCapture(False, "pi_9"))
    stripe.v1.checkout.sessions.retrieve.assert_called_once_with("cs_9", **(
        {"options": {"stripe_account": "acct_9"}} if connect else {}))
    stripe.v1.refunds.create.assert_not_called()


def test_an_expanded_processing_intent_is_not_mistaken_for_a_capture_id(stripe):
    stripe.v1.checkout.sessions.retrieve.return_value = NS(payment_status="unpaid", payment_intent={"id": "pi_9"})
    assert poll.poll_checkout(payment(stripe_checkout_session_id="cs_9"), NS(provider="raw")) == poll.PolledCapture(False)


@pytest.mark.parametrize("status,expected", [("processing", False), ("succeeded", True)])
def test_native_intent_capture_uses_received_amount_and_currency(monkeypatch, status, expected):
    retrieve = Mock(return_value={"status": status, "amount_received": 1234, "currency": "usd"})
    monkeypatch.setattr("apps.payments.stripe_client.retrieve_payment_intent", retrieve)
    source = NS(provider="raw")
    assert poll.poll_checkout(payment(stripe_payment_intent_id="pi_native"), source) == (
        poll.PolledCapture(True, "pi_native", 1234, "usd") if expected else poll.PolledCapture(False))
    retrieve.assert_called_once_with(source, "pi_native")


def test_no_checkout_handle_makes_no_provider_call(stripe):
    assert poll.poll_checkout(payment(), NS(provider="raw")) is None
    stripe.v1.checkout.sessions.retrieve.assert_not_called()


@pytest.fixture
def razorpay(monkeypatch):
    request = Mock()
    monkeypatch.setattr("apps.payments.providers.get_provider", lambda vendor: NS(_request=request))
    return request


@pytest.mark.parametrize("order", [True, False])
def test_razorpay_ignores_authorized_and_idless_captures_and_selects_the_real_capture(razorpay, order):
    rows = [{"id": "pay_auth", "payment_id": "pay_auth", "status": "authorized", "amount": 100},
            {"status": "captured", "amount": 100},
            {"id": "pay_good", "payment_id": "pay_good", "status": "captured", "amount": 850, "currency": "inr"}]
    razorpay.return_value = {"items" if order else "payments": rows}
    source = object()
    external_id = "order_9" if order else "plink_9"
    result = poll.poll_checkout(payment(provider="razorpay", external_order_id=external_id), source)
    assert result == poll.PolledCapture(True, "pay_good", 850, "inr" if order else "")
    razorpay.assert_called_once_with(source, "GET", "/orders/order_9/payments" if order else "/payment_links/plink_9")


@pytest.mark.parametrize("body", [None, {}, {"items": []}])
def test_empty_razorpay_results_are_unpaid(razorpay, body):
    razorpay.return_value = body
    assert poll.poll_checkout(payment(provider="razorpay", external_order_id="order_9"), object()) == poll.PolledCapture(False)


@pytest.mark.parametrize("status,expected", [("succeeded", "succeeded"), ("failed", "failed"),
                                             ("canceled", "failed"), ("requires_action", "pending")])
def test_stripe_refund_lookup_matches_our_metadata_and_the_refund_id(stripe, status, expected):
    stripe.v1.refunds.list.return_value = {"data": [
        {"id": "re_foreign", "metadata": {"refund_id": "8"}, "status": "succeeded"},
        {"metadata": {"refund_id": "9"}, "status": "succeeded"},
        {"id": "re_9", "metadata": {"refund_id": 9}, "status": status}]}
    refund = NS(pk=9, payment=payment(stripe_payment_intent_id="pi_9"), provider="stripe")
    source = NS(provider="connect", connected_account_id="acct_9")
    assert poll.find_refund(refund, source) == ("re_9", expected)
    stripe.v1.refunds.list.assert_called_once_with(params={"payment_intent": "pi_9", "limit": 100},
                                                  options={"stripe_account": "acct_9"})


@pytest.mark.parametrize("status,expected", [("processed", "succeeded"), ("failed", "failed"), ("pending", "pending")])
def test_razorpay_refund_lookup_matches_only_our_notes(razorpay, status, expected):
    razorpay.return_value = {"items": [{"id": "rf_wrong", "notes": {"refund_id": "other"}},
        {"id": "rf_9", "notes": {"refund_id": "9"}, "status": status}]}
    assert poll.find_refund(NS(pk=9, payment=payment(), provider="razorpay"), object()) == ("rf_9", expected)


@pytest.mark.parametrize("function", ["poll_checkout", "find_refund", "poll_refund"])
def test_provider_failure_returns_unknown_without_making_a_money_decision(stripe, function):
    stripe.v1.checkout.sessions.retrieve.side_effect = OSError("down")
    stripe.v1.refunds.list.side_effect = OSError("down")
    stripe.v1.refunds.retrieve.side_effect = OSError("down")
    row = payment(stripe_checkout_session_id="cs_9") if function == "poll_checkout" else NS(
        pk=9, payment=payment(), provider="stripe", external_refund_id="re_9")
    assert getattr(poll, function)(row, NS(provider="raw")) is None
    stripe.v1.refunds.create.assert_not_called()


@pytest.mark.parametrize("provider,status,expected", [
    ("stripe", "canceled", "failed"), ("stripe", "succeeded", "succeeded"), ("stripe", "unknown", "pending"),
    ("razorpay", "processed", "succeeded"), ("razorpay", "failed", "failed"), ("razorpay", "unknown", "pending")])
def test_refund_poll_never_treats_an_unknown_status_as_money_returned(stripe, razorpay, provider, status, expected):
    stripe.v1.refunds.retrieve.return_value = {"status": status}
    razorpay.return_value = {"status": status}
    refund = NS(pk=9, provider=provider, external_refund_id="rf_9")
    assert poll.poll_refund(refund, NS(provider="raw")) == expected
