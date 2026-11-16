"""Payments audit 0.12.0 (decision 256): online rail and offline settlement findings.

Pinned here: Connect money is never stranded by the hosting console switch, a mismatched
capture is always named in its audit entry, a charge being settled offline mints no new
online page, the gateway poll never kills a native rail, Razorpay links can be re-raised,
webhook replays settle once, and the ISO minor-unit exponents.
"""

import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.payments.capture_flags import captured_amount, differs
from apps.payments.checkout_coordination import PaymentSettlementPending, settlement_in_progress
from apps.payments.gateway_poll import _poll_attempt
from apps.payments.models import (
    Payment, PaymentClaim, PaymentDocument, PlatformStripeConnectSettings, SettlementConfirmation,
)
from apps.payments.money import minor_unit_exponent, to_minor_units
from apps.payments.online_settlement import settle_capture
from apps.payments.providers.base import CheckoutRequest
from apps.payments.providers.razorpay import RazorpayProvider
from apps.payments.resolution import source_for_payment
from apps.payments.services import create_checkout_url
from apps.payments_rail.provider_poll import PolledCapture
from tests.l5_local.helpers import dues, setup, switch
from tests.payments.recon_f_helpers import pending_charge
from tests.payments.test_razorpay_provider import configure_razorpay, sign

pytestmark = pytest.mark.django_db


# --- currency exponents ---------------------------------------------------------------

@pytest.mark.parametrize("currency,amount,minor", [
    ("jpy", "1500", 1500), ("jpy", "1500.50", 1501), ("kwd", "1.25", 1250), ("kwd", "0.01", 10),
    ("usd", "10.005", 1001), ("inr", "75.00", 7500), ("bhd", "2.10", 2100),
])
def test_minor_units_follow_iso_exponents(currency, amount, minor):
    assert to_minor_units(Decimal(amount), currency) == minor
    assert isinstance(to_minor_units(Decimal(amount), currency), int)


def test_exponent_table_covers_zero_and_three_decimal_currencies():
    assert minor_unit_exponent("JPY") == 0 and minor_unit_exponent("krw") == 0
    assert minor_unit_exponent("kwd") == 3 and minor_unit_exponent("OMR") == 3
    assert minor_unit_exponent("eur") == 2


def test_capture_comparison_uses_the_charge_currency_exponent():
    _space, _staff, payment = pending_charge("aud-kwd", amount="1.25", currency="kwd")
    assert not differs(payment, 1250, "KWD")
    assert differs(payment, 125, "kwd")  # a 2-decimal reading of a 3-decimal currency
    assert differs(payment, 1250, "usd")
    assert captured_amount(1250, "kwd", payment) == Decimal("1.25")
    _space, _staff, yen = pending_charge("aud-jpy", amount="1500.00", currency="jpy")
    assert not differs(yen, 1500, "jpy") and differs(yen, 150000, "jpy")


# --- capture mismatch is always audited -------------------------------------------------

@pytest.mark.parametrize("flags_on", [True, False])
def test_mismatched_capture_is_named_in_the_settlement_audit_even_with_flags_off(flags_on):
    space, _manager, payer = setup(f"aud-mismatch-{int(flags_on)}")
    switch(space, "billing.capture_flags", on=flags_on)
    payment = dues(space, payer, "10.00", provider=Payment.Provider.RAZORPAY)
    settle_capture(payment, provider=Payment.Provider.RAZORPAY, capture_id="pay_short", event_id="evt_short",
                   minor=900, currency="inr")
    entry = AuditLog.objects.get(action="payment.paid_online", target_id=str(payment.pk))
    assert entry.meta["capture_mismatch"] is True and entry.meta["captured_minor"] == 900
    assert entry.meta["captured_currency"] == "inr"


def test_matching_capture_carries_no_mismatch_marker():
    space, _manager, payer = setup("aud-match")
    payment = dues(space, payer, "10.00", provider=Payment.Provider.RAZORPAY)
    settle_capture(payment, provider=Payment.Provider.RAZORPAY, capture_id="pay_ok", event_id="evt_ok",
                   minor=1000, currency="inr")
    assert "capture_mismatch" not in AuditLog.objects.get(action="payment.paid_online",
                                                          target_id=str(payment.pk)).meta


# --- webhook replay and amount mismatch through the HTTP route --------------------------

def _capture_body(order_id, payment_id, amount, event="order.paid"):
    return json.dumps({"event": event, "payload": {
        "order": {"entity": {"id": order_id, "amount": amount, "currency": "USD"}},
        "payment": {"entity": {"id": payment_id, "order_id": order_id, "amount": amount, "currency": "USD"}},
    }}).encode()


def _post(space, body, event_id):
    return APIClient().post(reverse("razorpay-webhook", args=[space.public_code]), data=body,
                            content_type="application/json", HTTP_X_RAZORPAY_SIGNATURE=sign(body),
                            HTTP_X_RAZORPAY_EVENT_ID=event_id)


def test_razorpay_replay_settles_once_and_issues_one_receipt():
    space, _staff, payment = pending_charge("aud-replay", provider="razorpay", external_order_id="order_r1")
    configure_razorpay(space)
    body = _capture_body("order_r1", "pay_r1", 1000)
    for _ in range(3):
        assert _post(space, body, "evt_same").status_code == 200
    assert _post(space, _capture_body("order_r1", "pay_r1", 1000, "payment.captured"), "evt_other").status_code == 200
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PAID_ONLINE and payment.external_payment_id == "pay_r1"
    assert PaymentDocument.objects.filter(payment=payment, kind="receipt").count() == 1
    assert AuditLog.objects.filter(action="payment.paid_online", target_id=str(payment.pk)).count() == 1
    assert not AuditLog.objects.filter(action="payment.double_paid_refund_required",
                                       target_id=str(payment.pk)).exists()


def test_razorpay_underpayment_settles_flagged_and_holds_the_receipt():
    space, _staff, payment = pending_charge("aud-under", provider="razorpay", external_order_id="order_u1")
    switch(space, "billing.capture_flags")
    configure_razorpay(space)
    assert _post(space, _capture_body("order_u1", "pay_u1", 900), "evt_under").status_code == 200
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PAID_ONLINE
    assert payment.capture_flags.filter(kind="mismatch", resolution="").exists()


def test_forged_signature_never_settles():
    space, _staff, payment = pending_charge("aud-forged", provider="razorpay", external_order_id="order_f1")
    configure_razorpay(space)
    body = _capture_body("order_f1", "pay_f1", 1000)
    response = APIClient().post(reverse("razorpay-webhook", args=[space.public_code]), data=body,
                                content_type="application/json", HTTP_X_RAZORPAY_SIGNATURE="0" * 64,
                                HTTP_X_RAZORPAY_EVENT_ID="evt_forged")
    assert response.status_code == 400
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PENDING


# --- no new online page while an offline payment is being decided ----------------------

def test_open_claim_blocks_a_new_checkout():
    space, _manager, payer = setup("aud-claim-block", "billing.offline_claims")
    payment = dues(space, payer, "10.00")
    PaymentClaim.objects.create(makerspace=space, payment=payment, claimant=payer, reference="UTR12345678",
                                paid_on=timezone.localdate(), amount=payment.amount, currency=payment.currency)
    assert settlement_in_progress(payment)
    with pytest.raises(PaymentSettlementPending):
        create_checkout_url(payment.pk, actor=payer)


def test_awaiting_maker_checker_proposal_blocks_a_new_checkout(django_user_model):
    space, manager, payer = setup("aud-mc-block", "billing.maker_checker")
    payment = dues(space, payer, "10.00")
    SettlementConfirmation.objects.create(payment=payment, method="cash", reference="", received_at=timezone.now(),
                                          amount=payment.amount, currency=payment.currency, proposed_by=manager)
    assert settlement_in_progress(payment)
    with pytest.raises(PaymentSettlementPending):
        create_checkout_url(payment.pk, actor=payer)


def test_decided_claim_no_longer_blocks():
    space, _manager, payer = setup("aud-claim-done", "billing.offline_claims")
    payment = dues(space, payer, "10.00")
    PaymentClaim.objects.create(makerspace=space, payment=payment, claimant=payer, reference="UTR87654321",
                                paid_on=timezone.localdate(), amount=payment.amount, currency=payment.currency,
                                status=PaymentClaim.Status.REJECTED)
    assert not settlement_in_progress(payment)


# --- the gateway poll never kills a native rail -----------------------------------------

def test_poll_abandon_keeps_a_native_intent_payable():
    space, _manager, payer = setup("aud-native-abandon")
    payment = dues(space, payer, "10.00", provider=Payment.Provider.STRIPE)
    Payment.objects.filter(pk=payment.pk).update(online_rail="native_payment_intent",
                                                 stripe_payment_intent_id="pi_native_keep")
    payment.refresh_from_db()
    with patch("apps.payments.resolution.source_for_payment", return_value=object()), \
            patch("apps.payments_rail.provider_poll.poll_checkout", return_value=PolledCapture(False)), \
            patch("apps.payments.reconciliation_rail._expire_checkout_best_effort") as expire:
        assert _poll_attempt(payment, timezone.now() + timedelta(days=8))
    expire.assert_not_called()  # the intent is not cancelled at Stripe
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PENDING
    assert payment.stripe_payment_intent_id == "pi_native_keep" and payment.online_rail == "native_payment_intent"
    assert payment.stripe_checkout_session_expired_at is not None  # no longer polled


def test_poll_abandon_keeps_a_razorpay_native_order_matchable():
    space, _staff, payment = pending_charge("aud-native-rzp", provider="razorpay",
                                            online_rail="native_payment_intent", external_order_id="order_keep")
    configure_razorpay(space)
    with patch("apps.payments_rail.provider_poll.poll_checkout", return_value=PolledCapture(False)):
        assert _poll_attempt(payment, timezone.now() + timedelta(days=8))
    payment.refresh_from_db()
    assert payment.external_order_id == "order_keep"
    # A late capture of the retained order still settles the charge.
    assert _post(space, _capture_body("order_keep", "pay_late", 1000), "evt_late").status_code == 200
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PAID_ONLINE


# --- Razorpay links can be raised again after one expired -------------------------------

def _request(key):
    return CheckoutRequest(amount_minor=1000, currency="inr", description="Dues", reference="42",
                           success_url="https://x/ok", cancel_url="https://x/no", metadata={},
                           idempotency_key=key)


@pytest.mark.parametrize("key,expected", [
    ("payment-checkout-42-0", "42"),
    ("payment-checkout-42-1731000000123456", "42-1731000000123456"),
])
def test_razorpay_reference_id_is_unique_per_link_generation(key, expected):
    sent = {}

    def fake_request(_self, _source, _method, _path, body=None):
        sent.update(body or {})
        return {"id": "plink_1", "short_url": "https://rzp.io/x"}

    with patch.object(RazorpayProvider, "_request", fake_request):
        RazorpayProvider().create_checkout(object(), _request(key))
    assert sent["reference_id"] == expected and len(sent["reference_id"]) <= 40


# --- Connect money is not stranded by the hosting console switch ------------------------

def _configure_platform(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = False  # the console switch reads off
    PlatformStripeConnectSettings.load()
    PlatformStripeConnectSettings.objects.filter(pk=1).update(
        stripe_secret_key="fernet:x", stripe_webhook_secret="fernet:corrupt", stripe_connect_client_id="ca_x")


def test_connect_webhook_still_verifies_when_hosting_is_switched_off(settings):
    _configure_platform(settings)
    response = APIClient().post("/api/v1/webhooks/stripe/connect", b"{}", content_type="application/json",
                                HTTP_STRIPE_SIGNATURE="invalid", HTTP_HOST="localhost")
    # Not the dormant 404: the request reached signature verification (and failed it).
    assert response.status_code == 400


def test_existing_connect_charge_keeps_its_source_when_hosting_is_switched_off(settings):
    _configure_platform(settings)
    _space, _staff, payment = pending_charge("aud-connect-src", stripe_provider="connect",
                                             stripe_connected_account_id="acct_keep")
    with patch.object(PlatformStripeConnectSettings, "get_stripe_secret_key", return_value="sk_platform"), \
            patch.object(PlatformStripeConnectSettings, "get_stripe_webhook_secret", return_value="whsec_platform"):
        source = source_for_payment(payment)
    assert source is not None and source.provider == "connect" and source.connected_account_id == "acct_keep"


# --- Connect failure events reach the member ------------------------------------------

def test_connect_payment_failed_event_notifies_the_payer(settings):
    from apps.payments.services_connect_webhooks import apply_connect_webhook_event

    _space, _staff, payment = pending_charge("aud-connect-fail", stripe_provider="connect",
                                             stripe_connected_account_id="acct_fail",
                                             stripe_payment_intent_id="pi_fail")
    with patch("apps.payments.failure_notifications.notify_payment") as notify:
        apply_connect_webhook_event({"id": "evt_fail", "type": "payment_intent.payment_failed",
                                     "account": "acct_fail", "data": {"object": {"id": "pi_fail"}}})
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PENDING
    assert AuditLog.objects.filter(action="payment.failed", target_id=str(payment.pk)).exists()
    notify.assert_called_once()


# --- create_payment: one rounding rule and one duplicate signal (B-2, B-3) --------------

def _raise_dues(space, payer, amount, currency):
    from apps.makerspaces.models import MakerspaceMembership
    from apps.payments.services import create_payment

    membership = MakerspaceMembership.objects.get(makerspace=space, user=payer)
    return create_payment(makerspace=space, subject_type=Payment.SubjectType.MAKERSPACE_MEMBERSHIP,
                          subject_id=membership.pk, member=payer, amount=Decimal(amount), currency=currency,
                          created_by=payer)


@pytest.mark.parametrize("currency,amount,stored", [
    ("jpy", "1500.50", Decimal("1501")), ("jpy", "1500", Decimal("1500")),
    ("usd", "10.005", Decimal("10.01")), ("kwd", "1.25", Decimal("1.25")),
])
def test_create_payment_stores_what_the_provider_can_capture(currency, amount, stored):
    space, _manager, payer = setup(f"aud-round-{currency}-{amount.replace('.', '')}")
    payment = _raise_dues(space, payer, amount, currency)
    assert payment.amount == stored
    # quote = charge = capture: the provider amount is exactly the stored ledger amount.
    assert to_minor_units(payment.amount, currency) == int(stored.scaleb(minor_unit_exponent(currency)))
    assert AuditLog.objects.get(action="payment.created", target_id=str(payment.pk)).meta["amount"] == str(stored)


def test_a_second_raise_for_the_same_subject_is_an_integrity_error_not_a_500():
    from django.db import IntegrityError

    space, _manager, payer = setup("aud-dup-raise")
    first = _raise_dues(space, payer, "10.00", "inr")
    with pytest.raises(IntegrityError):
        _raise_dues(space, payer, "10.00", "inr")
    assert Payment.objects.filter(subject_type=first.subject_type, subject_id=first.subject_id).count() == 1


def test_unpaid_gifts_are_never_payment_reminders():
    from apps.payments.reminders import _payments

    space, _manager, payer = setup("aud-gift-remind", "billing.reminders")
    owed = dues(space, payer, "10.00", due_at=timezone.now())
    # bulk_create: the subject check is not under test here, only the reminder filter.
    [gift] = Payment.objects.bulk_create([Payment(
        makerspace=space, subject_type=Payment.SubjectType.DONATION, subject_id=987654, member=payer,
        amount=Decimal("5.00"), currency="inr", created_by=payer, due_at=timezone.now())])
    ids = set(_payments(space).values_list("pk", flat=True))
    assert owed.pk in ids and gift.pk not in ids
