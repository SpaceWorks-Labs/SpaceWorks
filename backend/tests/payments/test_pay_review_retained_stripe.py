"""PAY-REVIEW 0.12.0: Stripe charges raised before a switch to Razorpay keep their rail.

`raw_credentials_configured` follows the SELECTED provider, so after a switch to Razorpay it
read False and (a) the per-space Stripe webhook answered 400 to every event -- a refund raised
before the switch stayed PENDING forever and disputes were never ingested -- and (b)
`source_for_payment` returned None for the old Stripe rows, so they could not be refunded
online. Razorpay rows already kept their retained credentials; Stripe rows now do too, while
NEW checkouts still follow the selection.
"""

import hashlib
import hmac
import json
import time
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.payments.models import Payment, Refund
from apps.payments.resolution import resolve_payment_source, source_for_payment
from tests.payments.recon_f_helpers import pending_charge
from tests.payments.test_models import configured_settings

pytestmark = pytest.mark.django_db
WEBHOOK_SECRET = "whsec_test_secret"


def _signature(body):
    timestamp = int(time.time())
    digest = hmac.new(WEBHOOK_SECRET.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def _paid_stripe_charge_then_switch(slug):
    space, staff, payment = pending_charge(slug, provider="stripe")
    Payment.objects.filter(pk=payment.pk).update(status=Payment.Status.PAID_ONLINE,
                                                 stripe_payment_intent_id=f"pi_{slug}")
    merchant = configured_settings(space)
    merchant.provider = "razorpay"
    merchant.razorpay_key_id = "rzp_test_key"
    merchant.set_razorpay_key_secret("rzp_test_secret")
    merchant.set_razorpay_webhook_secret("rzp_webhook_secret")
    merchant.save()
    assert merchant.provider == "razorpay"  # the selection moved; the retained Stripe keys stay on the row
    return space, staff, Payment.objects.get(pk=payment.pk)


def test_old_stripe_charge_keeps_its_source_after_a_switch_to_razorpay():
    space, _staff, payment = _paid_stripe_charge_then_switch("prv-source")
    source = source_for_payment(payment)
    assert source is not None and source.vendor == "stripe" and source.secret_key == "sk_test_secret"
    # New checkouts still follow the selection.
    assert resolve_payment_source(space).vendor == "razorpay"


def test_stripe_refund_webhook_settles_after_a_switch_to_razorpay():
    space, staff, payment = _paid_stripe_charge_then_switch("prv-refund")
    refund = Refund.objects.create(payment=payment, amount=Decimal("10.00"), currency="usd",
                                   provider="stripe", created_by=staff)
    body = json.dumps({
        "id": "evt_prv_refund", "object": "event", "type": "refund.updated",
        "data": {"object": {"id": "re_prv", "object": "refund", "status": "succeeded",
                            "payment_intent": payment.stripe_payment_intent_id, "amount": 1000}},
    }, separators=(",", ":")).encode()
    response = APIClient().generic("POST", f"/api/v1/webhooks/stripe/{space.public_code}", body,
                                   content_type="application/json", HTTP_STRIPE_SIGNATURE=_signature(body))
    assert response.status_code == 200
    refund.refresh_from_db()
    assert refund.status == Refund.Status.SUCCEEDED and refund.external_refund_id == "re_prv"


def test_stripe_webhook_still_refuses_without_retained_stripe_keys():
    space, _staff, _payment = pending_charge("prv-no-keys", provider="stripe")
    body = b'{"id":"evt_x","object":"event","type":"refund.updated","data":{"object":{}}}'
    response = APIClient().generic("POST", f"/api/v1/webhooks/stripe/{space.public_code}", body,
                                   content_type="application/json", HTTP_STRIPE_SIGNATURE=_signature(body))
    assert response.status_code == 400
