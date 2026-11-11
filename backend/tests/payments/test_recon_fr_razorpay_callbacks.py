"""Historical Razorpay collections survive a switch of the new-payment vendor."""
import json

import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.payments.credential_validation import update_payment_settings
from apps.payments.models import Payment, PaymentDocument, ProcessedStripeEvent
from apps.payments.reconciliation import reconcile_payments
from apps.payments.resolution import resolve_payment_source, source_for_payment
from tests.payments.recon_f_helpers import pending_charge
from tests.payments.test_razorpay_provider import configure_razorpay, sign
from tests.return_helpers import make_space, settlement_details

pytestmark = pytest.mark.django_db


def capture_body(payment, event):
    return json.dumps({"event": event, "payload": {
        "order": {"entity": {"id": payment.external_order_id, "amount": 1000, "currency": "USD"}},
        "payment": {"entity": {"id": "pay_late", "order_id": payment.external_order_id,
                               "amount": 1000, "currency": "USD"}},
    }}).encode()


def post_capture(client, space, body, event_id, signature):
    return client.post(reverse("razorpay-webhook", args=[space.public_code]), data=body,
        content_type="application/json", HTTP_X_RAZORPAY_SIGNATURE=signature,
        HTTP_X_RAZORPAY_EVENT_ID=event_id)


@pytest.mark.parametrize("terminal", ["waived", "paid_offline"])
@pytest.mark.parametrize("stripe_configured", [False, True])
def test_late_native_capture_after_switch_settles_or_flags_excess_once(client, terminal, stripe_configured):
    space, staff, payment = pending_charge("fr-late-capture", provider="razorpay",
        online_rail="native_payment_intent", external_order_id="order_late")
    merchant = configure_razorpay(space)
    if stripe_configured:
        merchant.set_stripe_secret_key("sk_retained")
        merchant.set_stripe_webhook_secret("whsec_retained")
        merchant.save()
    reconcile_payments(actor=staff, makerspace_id=space.pk, payment_ids=[payment.pk],
        target_status=terminal, settlement=settlement_details() if terminal == "paid_offline" else None)
    payment.refresh_from_db()
    assert payment.stripe_checkout_session_expired_at is not None
    update_payment_settings(merchant, {"provider": "stripe"})
    new_source = resolve_payment_source(space)
    if stripe_configured:
        assert new_source.vendor == "stripe"
    else:
        assert new_source is None
    assert source_for_payment(payment).vendor == "razorpay"
    before = Payment.objects.filter(pk=payment.pk).values().get()

    for event, event_id in (("order.paid", "evt_order"), ("payment.captured", "evt_capture"),
                            ("payment.captured", "evt_capture")):
        body = capture_body(payment, event)
        assert post_capture(client, space, body, event_id, sign(body)).status_code == 200

    payment.refresh_from_db()
    receipts = PaymentDocument.objects.filter(payment=payment, kind="receipt")
    assert receipts.count() == 1
    excess = AuditLog.objects.filter(makerspace=space, target_id=str(payment.pk),
        action="payment.double_paid_refund_required")
    if terminal == "waived":
        assert payment.status == "paid_online" and payment.external_payment_id == "pay_late"
        assert receipts.get().settlement_method == "razorpay"
        assert not excess.exists()
    else:
        assert Payment.objects.filter(pk=payment.pk).values().get() == before
        assert receipts.get().settlement_method == "cash"
        assert excess.count() == 1
        assert excess.get().meta["provider_payment_id"] == "pay_late"
    assert ProcessedStripeEvent.objects.filter(makerspace=space, provider="razorpay").count() == 2


@pytest.mark.parametrize("invalid", ["forged", "missing", "other_tenant"])
def test_retained_credentials_still_require_the_addressed_tenants_signature(client, invalid):
    space, _, payment = pending_charge("fr-rejected-capture", provider="razorpay",
        online_rail="native_payment_intent", external_order_id="order_rejected")
    merchant = configure_razorpay(space)
    merchant.provider = "stripe"
    merchant.save(update_fields=["provider"])
    addressed = make_space("fr-other-tenant") if invalid == "other_tenant" else space
    if invalid == "other_tenant":
        configure_razorpay(addressed, webhook_secret="different-tenant-secret")
    body = capture_body(payment, "payment.captured")
    signature = sign(body) if invalid == "other_tenant" else "forged" if invalid == "forged" else ""
    assert post_capture(client, addressed, body, "evt_rejected", signature).status_code == 400
    payment.refresh_from_db()
    assert payment.status == "pending"
    assert not ProcessedStripeEvent.objects.exists()
    assert not PaymentDocument.objects.filter(payment=payment).exists()
